"""
Unit tests for authorization middleware.

Tests cover:
- Authentication decorator for protected routes
- Cassette ownership checking
- User isolation for cassette access

Requirements: 8.2, 8.3
"""

import pytest
from flask import Flask, jsonify
from app.services.authorization import (
    require_auth,
    require_cassette_ownership,
    check_cassette_ownership,
    get_user_cassettes,
    can_access_cassette
)
from app.services.auth import AuthService
from app.models.user import User
from app.models.cassette import Cassette
from app.models.part import Part
from app.models.database import get_database


@pytest.fixture
def app():
    """Create a Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def setup_database():
    """Set up a fresh database for each test."""
    import tempfile
    import os
    
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    # Set the database path in environment
    os.environ['DATABASE_PATH'] = db_path
    
    # Reset the global database instance
    import app.models.database as db_module
    db_module._db_instance = None
    
    # Initialize the database
    db = get_database(db_path)
    db.initialize_schema()
    
    yield
    
    # Clean up
    AuthService.clear_all_sessions()
    
    # Remove temporary database file
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def test_user():
    """Create a test user."""
    return User.create("testuser", "password123")


@pytest.fixture
def test_user2():
    """Create a second test user."""
    return User.create("testuser2", "password456")


@pytest.fixture
def test_session(test_user):
    """Create a test session."""
    result = AuthService.login("testuser", "password123")
    return result['session_id']


@pytest.fixture
def test_parts():
    """Create test parts for cassette assembly."""
    part1 = Part.create(
        name="Test Part 1",
        part_type="Coding",
        sequence="AAAATTTTCCCCGGGG",
        overhang_5prime="AAAA",
        overhang_3prime="TTTT",
        lab_source="Test Lab",
        contributor="testuser"
    )
    part2 = Part.create(
        name="Test Part 2",
        part_type="NonCodingPromoter",
        sequence="TTTTCCCCGGGGAAAA",
        overhang_5prime="TTTT",
        overhang_3prime="CCCC",
        lab_source="Test Lab",
        contributor="testuser"
    )
    return [part1, part2]


@pytest.fixture
def test_cassette(test_user, test_parts):
    """Create a test cassette."""
    return Cassette.create(
        name="Test Cassette",
        owner_id=test_user.id,
        part_ids=[p.id for p in test_parts],
        assembled_sequence="AAAATTTTCCCCGGGGAAAA"
    )


class TestRequireAuthDecorator:
    """Tests for the require_auth decorator."""
    
    def test_require_auth_with_valid_session_header(self, app, client, test_user, test_session):
        """Test that require_auth allows access with valid session in header."""
        @app.route('/test')
        @require_auth
        def test_route(user):
            return jsonify({'username': user.username})
        
        response = client.get('/test', headers={'X-Session-ID': test_session})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['username'] == 'testuser'
    
    def test_require_auth_with_valid_session_cookie(self, app, client, test_user, test_session):
        """Test that require_auth allows access with valid session in cookie."""
        @app.route('/test')
        @require_auth
        def test_route(user):
            return jsonify({'username': user.username})
        
        client.set_cookie('session_id', test_session)
        response = client.get('/test')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['username'] == 'testuser'
    
    def test_require_auth_without_session(self, app, client):
        """Test that require_auth denies access without session."""
        @app.route('/test')
        @require_auth
        def test_route(user):
            return jsonify({'username': user.username})
        
        response = client.get('/test')
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'Authentication required'
        assert 'No session ID provided' in data['message']
    
    def test_require_auth_with_invalid_session(self, app, client):
        """Test that require_auth denies access with invalid session."""
        @app.route('/test')
        @require_auth
        def test_route(user):
            return jsonify({'username': user.username})
        
        response = client.get('/test', headers={'X-Session-ID': 'invalid-session-id'})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'Authentication required'
        assert 'Invalid or expired session' in data['message']
    
    def test_require_auth_with_expired_session(self, app, client, test_user, test_session):
        """Test that require_auth denies access with expired session."""
        @app.route('/test')
        @require_auth
        def test_route(user):
            return jsonify({'username': user.username})
        
        # Logout to invalidate session
        AuthService.logout(test_session)
        
        response = client.get('/test', headers={'X-Session-ID': test_session})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'Authentication required'


class TestCheckCassetteOwnership:
    """Tests for the check_cassette_ownership function."""
    
    def test_check_ownership_valid_owner(self, test_user, test_cassette):
        """Test checking ownership for the actual owner."""
        is_owner, error = check_cassette_ownership(test_cassette.id, test_user.id)
        
        assert is_owner is True
        assert error is None
    
    def test_check_ownership_different_user(self, test_user2, test_cassette):
        """Test checking ownership for a different user."""
        is_owner, error = check_cassette_ownership(test_cassette.id, test_user2.id)
        
        assert is_owner is False
        assert error == "Access denied to cassette"
    
    def test_check_ownership_nonexistent_cassette(self, test_user):
        """Test checking ownership for a cassette that doesn't exist."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        is_owner, error = check_cassette_ownership(fake_id, test_user.id)
        
        assert is_owner is False
        assert "not found" in error


class TestRequireCassetteOwnershipDecorator:
    """Tests for the require_cassette_ownership decorator."""
    
    def test_require_ownership_valid_owner(self, app, client, test_user, test_session, test_cassette):
        """Test that require_cassette_ownership allows access for owner."""
        @app.route('/cassettes/<cassette_id>')
        @require_cassette_ownership
        def test_route(user, cassette, cassette_id):
            return jsonify({
                'cassette_name': cassette.name,
                'user_name': user.username
            })
        
        response = client.get(
            f'/cassettes/{test_cassette.id}',
            headers={'X-Session-ID': test_session}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['cassette_name'] == 'Test Cassette'
        assert data['user_name'] == 'testuser'
    
    def test_require_ownership_different_user(self, app, client, test_user2, test_cassette):
        """Test that require_cassette_ownership denies access for non-owner."""
        @app.route('/cassettes/<cassette_id>')
        @require_cassette_ownership
        def test_route(user, cassette, cassette_id):
            return jsonify({'cassette_name': cassette.name})
        
        # Login as different user
        result = AuthService.login("testuser2", "password456")
        session_id = result['session_id']
        
        response = client.get(
            f'/cassettes/{test_cassette.id}',
            headers={'X-Session-ID': session_id}
        )
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'Forbidden'
        assert 'Access denied' in data['message']
    
    def test_require_ownership_nonexistent_cassette(self, app, client, test_user, test_session):
        """Test that require_cassette_ownership returns 404 for nonexistent cassette."""
        @app.route('/cassettes/<cassette_id>')
        @require_cassette_ownership
        def test_route(user, cassette, cassette_id):
            return jsonify({'cassette_name': cassette.name})
        
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(
            f'/cassettes/{fake_id}',
            headers={'X-Session-ID': test_session}
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['error'] == 'Not found'
    
    def test_require_ownership_without_session(self, app, client, test_cassette):
        """Test that require_cassette_ownership requires authentication."""
        @app.route('/cassettes/<cassette_id>')
        @require_cassette_ownership
        def test_route(user, cassette, cassette_id):
            return jsonify({'cassette_name': cassette.name})
        
        response = client.get(f'/cassettes/{test_cassette.id}')
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'Authentication required'


class TestGetUserCassettes:
    """Tests for the get_user_cassettes function."""
    
    def test_get_user_cassettes_single_cassette(self, test_user, test_cassette):
        """Test getting cassettes for a user with one cassette."""
        cassettes = get_user_cassettes(test_user.id)
        
        assert len(cassettes) == 1
        assert cassettes[0].id == test_cassette.id
        assert cassettes[0].owner_id == test_user.id
    
    def test_get_user_cassettes_multiple_cassettes(self, test_user, test_parts):
        """Test getting cassettes for a user with multiple cassettes."""
        cassette1 = Cassette.create(
            name="Cassette 1",
            owner_id=test_user.id,
            part_ids=[p.id for p in test_parts],
            assembled_sequence="AAAATTTTCCCCGGGGAAAA"
        )
        cassette2 = Cassette.create(
            name="Cassette 2",
            owner_id=test_user.id,
            part_ids=[p.id for p in test_parts],
            assembled_sequence="AAAATTTTCCCCGGGGAAAA"
        )
        
        cassettes = get_user_cassettes(test_user.id)
        
        assert len(cassettes) == 2
        cassette_ids = [c.id for c in cassettes]
        assert cassette1.id in cassette_ids
        assert cassette2.id in cassette_ids
    
    def test_get_user_cassettes_no_cassettes(self, test_user):
        """Test getting cassettes for a user with no cassettes."""
        cassettes = get_user_cassettes(test_user.id)
        
        assert len(cassettes) == 0
    
    def test_get_user_cassettes_isolation(self, test_user, test_user2, test_parts):
        """Test that users only see their own cassettes."""
        # Create cassettes for both users
        cassette1 = Cassette.create(
            name="User 1 Cassette",
            owner_id=test_user.id,
            part_ids=[p.id for p in test_parts],
            assembled_sequence="AAAATTTTCCCCGGGGAAAA"
        )
        cassette2 = Cassette.create(
            name="User 2 Cassette",
            owner_id=test_user2.id,
            part_ids=[p.id for p in test_parts],
            assembled_sequence="AAAATTTTCCCCGGGGAAAA"
        )
        
        # Get cassettes for user 1
        user1_cassettes = get_user_cassettes(test_user.id)
        assert len(user1_cassettes) == 1
        assert user1_cassettes[0].id == cassette1.id
        
        # Get cassettes for user 2
        user2_cassettes = get_user_cassettes(test_user2.id)
        assert len(user2_cassettes) == 1
        assert user2_cassettes[0].id == cassette2.id


class TestCanAccessCassette:
    """Tests for the can_access_cassette function."""
    
    def test_can_access_own_cassette(self, test_user, test_cassette):
        """Test that user can access their own cassette."""
        can_access = can_access_cassette(test_cassette.id, test_user.id)
        
        assert can_access is True
    
    def test_cannot_access_other_user_cassette(self, test_user2, test_cassette):
        """Test that user cannot access another user's cassette."""
        can_access = can_access_cassette(test_cassette.id, test_user2.id)
        
        assert can_access is False
    
    def test_cannot_access_nonexistent_cassette(self, test_user):
        """Test that accessing nonexistent cassette returns False."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        can_access = can_access_cassette(fake_id, test_user.id)
        
        assert can_access is False


class TestUserIsolation:
    """Integration tests for user isolation."""
    
    def test_complete_user_isolation_workflow(self, test_user, test_user2, test_parts):
        """Test complete workflow ensuring users cannot access each other's cassettes."""
        # User 1 creates a cassette
        cassette1 = Cassette.create(
            name="User 1 Private Cassette",
            owner_id=test_user.id,
            part_ids=[p.id for p in test_parts],
            assembled_sequence="AAAATTTTCCCCGGGGAAAA"
        )
        
        # User 2 creates a cassette
        cassette2 = Cassette.create(
            name="User 2 Private Cassette",
            owner_id=test_user2.id,
            part_ids=[p.id for p in test_parts],
            assembled_sequence="AAAATTTTCCCCGGGGAAAA"
        )
        
        # User 1 can access their own cassette
        assert can_access_cassette(cassette1.id, test_user.id) is True
        user1_cassettes = get_user_cassettes(test_user.id)
        assert len(user1_cassettes) == 1
        assert user1_cassettes[0].id == cassette1.id
        
        # User 1 cannot access User 2's cassette
        assert can_access_cassette(cassette2.id, test_user.id) is False
        
        # User 2 can access their own cassette
        assert can_access_cassette(cassette2.id, test_user2.id) is True
        user2_cassettes = get_user_cassettes(test_user2.id)
        assert len(user2_cassettes) == 1
        assert user2_cassettes[0].id == cassette2.id
        
        # User 2 cannot access User 1's cassette
        assert can_access_cassette(cassette1.id, test_user2.id) is False
    
    def test_ownership_check_prevents_unauthorized_access(self, test_user, test_user2, test_cassette):
        """Test that ownership check prevents unauthorized access."""
        # Owner can access
        is_owner, error = check_cassette_ownership(test_cassette.id, test_user.id)
        assert is_owner is True
        assert error is None
        
        # Non-owner cannot access
        is_owner, error = check_cassette_ownership(test_cassette.id, test_user2.id)
        assert is_owner is False
        assert error == "Access denied to cassette"
