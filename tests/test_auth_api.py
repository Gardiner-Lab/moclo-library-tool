"""
Unit tests for authentication API endpoints.

Tests cover:
- POST /api/auth/register - User registration
- POST /api/auth/login - User login
- POST /api/auth/logout - User logout
- GET /api/auth/session - Check session status

Requirements: 9.1, 9.2, 9.3, 9.6
"""

import pytest
import os
import tempfile
import json
from app.main import create_app
from app.services.auth import AuthService
from app.models import database as db_module
from app.models.database import Database


@pytest.fixture
def app():
    """Create and configure a test Flask application."""
    # Create a temporary database
    db_fd, db_path = tempfile.mkstemp()
    
    # Create app with test configuration
    test_app = create_app()
    test_app.config['TESTING'] = True
    test_app.config['DATABASE_PATH'] = db_path
    test_app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Initialize database
    db = Database(db_path)
    db.initialize_schema()
    db_module._db_instance = db
    
    # Clear sessions
    AuthService.clear_all_sessions()
    
    yield test_app
    
    # Cleanup
    AuthService.clear_all_sessions()
    db_module._db_instance = None
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


class TestRegisterEndpoint:
    """Tests for POST /api/auth/register endpoint."""
    
    def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        
        assert 'user' in data
        assert data['user']['username'] == 'testuser'
        assert 'id' in data['user']
        assert 'created_at' in data['user']
        assert 'password_hash' not in data['user']
        assert data['message'] == 'User registered successfully'
    
    def test_register_duplicate_username(self, client):
        """Test registration with duplicate username fails."""
        # Register first user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        # Attempt to register with same username
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'different_password'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'error' in data
        assert 'already exists' in data['error'].lower()
    
    def test_register_missing_username(self, client):
        """Test registration without username fails."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'username' in data['error'].lower()
    
    def test_register_missing_password(self, client):
        """Test registration without password fails."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'password' in data['error'].lower()
    
    def test_register_empty_username(self, client):
        """Test registration with empty username fails."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': '',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_register_empty_password(self, client):
        """Test registration with empty password fails."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': ''
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_register_no_json_body(self, client):
        """Test registration without JSON body fails."""
        response = client.post('/api/auth/register')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'json' in data['error'].lower()


class TestLoginEndpoint:
    """Tests for POST /api/auth/login endpoint."""
    
    def test_login_success(self, client):
        """Test successful login."""
        # Register a user first
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        # Login
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'user' in data
        assert data['user']['username'] == 'testuser'
        assert 'session_id' in data
        assert 'expires_at' in data
        assert data['message'] == 'Login successful'
        assert 'password_hash' not in data['user']
    
    def test_login_creates_session_cookie(self, client):
        """Test that login creates a session cookie."""
        # Register a user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        # Login
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        # Check that session cookie is set
        assert response.status_code == 200
        # Flask test client stores session in context
    
    def test_login_invalid_username(self, client):
        """Test login with non-existent username fails."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'nonexistent',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
        assert 'invalid' in data['error'].lower()
    
    def test_login_invalid_password(self, client):
        """Test login with incorrect password fails."""
        # Register a user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        # Attempt login with wrong password
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'testuser',
                'password': 'wrongpassword'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
        assert 'invalid' in data['error'].lower()
    
    def test_login_missing_credentials(self, client):
        """Test login without credentials fails."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_login_no_json_body(self, client):
        """Test login without JSON body fails."""
        response = client.post('/api/auth/login')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'json' in data['error'].lower()


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout endpoint."""
    
    def test_logout_success(self, client):
        """Test successful logout."""
        # Register and login
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        login_response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        login_data = json.loads(login_response.data)
        session_id = login_data['session_id']
        
        # Logout
        response = client.post('/api/auth/logout')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['message'] == 'Logout successful'
        
        # Verify session is no longer valid
        assert not AuthService.validate_session(session_id)
    
    def test_logout_without_session(self, client):
        """Test logout without active session fails."""
        response = client.post('/api/auth/logout')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_logout_clears_session(self, client):
        """Test that logout clears the session."""
        # Register and login
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        # Logout
        client.post('/api/auth/logout')
        
        # Try to access session endpoint
        response = client.get('/api/auth/session')
        data = json.loads(response.data)
        
        assert data['authenticated'] is False


class TestSessionEndpoint:
    """Tests for GET /api/auth/session endpoint."""
    
    def test_session_authenticated(self, client):
        """Test session endpoint with valid session."""
        # Register and login
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        login_response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        login_data = json.loads(login_response.data)
        
        # Check session
        response = client.get('/api/auth/session')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['authenticated'] is True
        assert 'user' in data
        assert data['user']['username'] == 'testuser'
        assert 'session_id' in data
        assert data['session_id'] == login_data['session_id']
    
    def test_session_not_authenticated(self, client):
        """Test session endpoint without session."""
        response = client.get('/api/auth/session')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['authenticated'] is False
        assert 'user' not in data
        assert 'session_id' not in data
    
    def test_session_expired(self, client):
        """Test session endpoint with expired session."""
        # Register and login
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        login_response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        
        login_data = json.loads(login_response.data)
        session_id = login_data['session_id']
        
        # Manually expire the session
        from datetime import datetime, timedelta, timezone
        session = AuthService._sessions[session_id]
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Check session
        response = client.get('/api/auth/session')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['authenticated'] is False


class TestIntegrationWorkflows:
    """Integration tests for complete authentication workflows."""
    
    def test_complete_auth_flow(self, client):
        """Test complete authentication flow: register -> login -> check session -> logout."""
        # Register
        register_response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        assert register_response.status_code == 201
        
        # Login
        login_response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'testuser',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        assert login_response.status_code == 200
        
        # Check session
        session_response = client.get('/api/auth/session')
        session_data = json.loads(session_response.data)
        assert session_data['authenticated'] is True
        
        # Logout
        logout_response = client.post('/api/auth/logout')
        assert logout_response.status_code == 200
        
        # Check session after logout
        session_response2 = client.get('/api/auth/session')
        session_data2 = json.loads(session_response2.data)
        assert session_data2['authenticated'] is False
    
    def test_multiple_users_isolation(self, client):
        """Test that multiple users have isolated sessions."""
        # Register two users
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'user1',
                'password': 'password1'
            }),
            content_type='application/json'
        )
        
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'user2',
                'password': 'password2'
            }),
            content_type='application/json'
        )
        
        # Login as user1
        login1_response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'user1',
                'password': 'password1'
            }),
            content_type='application/json'
        )
        login1_data = json.loads(login1_response.data)
        
        # Check session shows user1
        session_response = client.get('/api/auth/session')
        session_data = json.loads(session_response.data)
        assert session_data['user']['username'] == 'user1'
        
        # Logout user1
        client.post('/api/auth/logout')
        
        # Login as user2
        login2_response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'user2',
                'password': 'password2'
            }),
            content_type='application/json'
        )
        login2_data = json.loads(login2_response.data)
        
        # Check session shows user2
        session_response2 = client.get('/api/auth/session')
        session_data2 = json.loads(session_response2.data)
        assert session_data2['user']['username'] == 'user2'
        
        # Verify session IDs are different
        assert login1_data['session_id'] != login2_data['session_id']
