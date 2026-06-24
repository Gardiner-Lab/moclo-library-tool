"""
Unit tests for the authentication service.

Tests cover:
- User registration with password hashing
- Login with credential validation
- Session creation and management
- Logout with session termination

Requirements: 9.1, 9.2, 9.3, 9.4, 9.6
"""

import pytest
import os
import tempfile
from datetime import datetime, timedelta, timezone
from app.services.auth import AuthService, Session
from app.models.user import User
from app.models.database import Database


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Set up and tear down for each test."""
    # Create a temporary database for each test
    db_fd, db_path = tempfile.mkstemp()
    
    # Initialize database
    from app.models import database as db_module
    db = Database(db_path)
    db.initialize_schema()
    
    # Set the database as the singleton instance
    db_module._db_instance = db
    
    # Clear sessions before each test
    AuthService.clear_all_sessions()
    
    yield
    
    # Clear sessions after each test
    AuthService.clear_all_sessions()
    
    # Cleanup database
    db_module._db_instance = None
    os.close(db_fd)
    os.unlink(db_path)


class TestUserRegistration:
    """Tests for user registration functionality."""
    
    def test_register_new_user_success(self):
        """Test successful registration of a new user."""
        # Register a new user
        result = AuthService.register("testuser", "password123")
        
        # Verify result contains user data
        assert 'id' in result
        assert result['username'] == "testuser"
        assert 'created_at' in result
        assert 'password_hash' not in result  # Password should not be in result
        
        # Verify user was created in database
        user = User.get_by_username("testuser")
        assert user is not None
        assert user.username == "testuser"
        assert user.password_hash is not None
    
    def test_register_hashes_password(self):
        """Test that registration hashes the password."""
        # Register a user
        AuthService.register("testuser", "password123")
        
        # Retrieve user from database
        user = User.get_by_username("testuser")
        
        # Verify password is hashed (not plain text)
        assert user.password_hash != "password123"
        assert len(user.password_hash) > 20  # Bcrypt hashes are long
        
        # Verify password can be verified
        assert User.verify_password("password123", user.password_hash)
    
    def test_register_duplicate_username_fails(self):
        """Test that registering with an existing username fails."""
        # Register first user
        AuthService.register("testuser", "password123")
        
        # Attempt to register with same username
        with pytest.raises(ValueError, match="already exists"):
            AuthService.register("testuser", "different_password")
    
    def test_register_empty_username_fails(self):
        """Test that registration with empty username fails."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            AuthService.register("", "password123")
        
        with pytest.raises(ValueError, match="Username cannot be empty"):
            AuthService.register("   ", "password123")
    
    def test_register_empty_password_fails(self):
        """Test that registration with empty password fails."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            AuthService.register("testuser", "")
        
        with pytest.raises(ValueError, match="Password cannot be empty"):
            AuthService.register("testuser", "   ")
    
    def test_register_trims_username(self):
        """Test that registration trims whitespace from username."""
        result = AuthService.register("  testuser  ", "password123")
        
        assert result['username'] == "testuser"
        
        user = User.get_by_username("testuser")
        assert user is not None
        assert user.username == "testuser"


class TestUserLogin:
    """Tests for user login functionality."""
    
    def test_login_success(self):
        """Test successful login with valid credentials."""
        # Register a user
        AuthService.register("testuser", "password123")
        
        # Login with correct credentials
        result = AuthService.login("testuser", "password123")
        
        # Verify result contains session data
        assert 'session_id' in result
        assert 'user' in result
        assert 'expires_at' in result
        
        # Verify user data
        assert result['user']['username'] == "testuser"
        assert 'password_hash' not in result['user']
        
        # Verify session ID is a valid UUID
        assert len(result['session_id']) == 36  # UUID format
    
    def test_login_creates_session(self):
        """Test that login creates a valid session."""
        # Register and login
        AuthService.register("testuser", "password123")
        result = AuthService.login("testuser", "password123")
        
        session_id = result['session_id']
        
        # Verify session exists and is valid
        session = AuthService.get_session(session_id)
        assert session is not None
        assert session.username == "testuser"
        assert not session.is_expired()
    
    def test_login_invalid_username(self):
        """Test login with non-existent username fails."""
        with pytest.raises(ValueError, match="Invalid username or password"):
            AuthService.login("nonexistent", "password123")
    
    def test_login_invalid_password(self):
        """Test login with incorrect password fails."""
        # Register a user
        AuthService.register("testuser", "password123")
        
        # Attempt login with wrong password
        with pytest.raises(ValueError, match="Invalid username or password"):
            AuthService.login("testuser", "wrongpassword")
    
    def test_login_empty_credentials(self):
        """Test login with empty credentials fails."""
        with pytest.raises(ValueError, match="Invalid username or password"):
            AuthService.login("", "password123")
        
        with pytest.raises(ValueError, match="Invalid username or password"):
            AuthService.login("testuser", "")
    
    def test_login_multiple_sessions(self):
        """Test that a user can have multiple active sessions."""
        # Register a user
        AuthService.register("testuser", "password123")
        
        # Login twice
        result1 = AuthService.login("testuser", "password123")
        result2 = AuthService.login("testuser", "password123")
        
        # Verify both sessions are different and valid
        assert result1['session_id'] != result2['session_id']
        assert AuthService.validate_session(result1['session_id'])
        assert AuthService.validate_session(result2['session_id'])


class TestSessionManagement:
    """Tests for session management functionality."""
    
    def test_get_session_valid(self):
        """Test retrieving a valid session."""
        # Register and login
        AuthService.register("testuser", "password123")
        result = AuthService.login("testuser", "password123")
        
        session_id = result['session_id']
        
        # Retrieve session
        session = AuthService.get_session(session_id)
        
        assert session is not None
        assert session.session_id == session_id
        assert session.username == "testuser"
    
    def test_get_session_invalid_id(self):
        """Test retrieving session with invalid ID returns None."""
        session = AuthService.get_session("invalid-session-id")
        assert session is None
    
    def test_get_session_empty_id(self):
        """Test retrieving session with empty ID returns None."""
        session = AuthService.get_session("")
        assert session is None
    
    def test_validate_session_valid(self):
        """Test validating a valid session."""
        # Register and login
        AuthService.register("testuser", "password123")
        result = AuthService.login("testuser", "password123")
        
        # Validate session
        is_valid = AuthService.validate_session(result['session_id'])
        assert is_valid is True
    
    def test_validate_session_invalid(self):
        """Test validating an invalid session."""
        is_valid = AuthService.validate_session("invalid-session-id")
        assert is_valid is False
    
    def test_get_user_from_session(self):
        """Test retrieving user from a valid session."""
        # Register and login
        AuthService.register("testuser", "password123")
        result = AuthService.login("testuser", "password123")
        
        # Get user from session
        user = AuthService.get_user_from_session(result['session_id'])
        
        assert user is not None
        assert user.username == "testuser"
        assert user.id == result['user']['id']
    
    def test_get_user_from_invalid_session(self):
        """Test retrieving user from invalid session returns None."""
        user = AuthService.get_user_from_session("invalid-session-id")
        assert user is None
    
    def test_session_expiration(self):
        """Test that expired sessions are not valid."""
        # Register and login
        AuthService.register("testuser", "password123")
        result = AuthService.login("testuser", "password123")
        
        session_id = result['session_id']
        
        # Manually expire the session
        session = AuthService._sessions[session_id]
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Verify session is now invalid
        assert AuthService.validate_session(session_id) is False
        assert AuthService.get_session(session_id) is None
    
    def test_session_to_dict(self):
        """Test session to_dict method."""
        # Register and login
        AuthService.register("testuser", "password123")
        result = AuthService.login("testuser", "password123")
        
        session = AuthService.get_session(result['session_id'])
        session_dict = session.to_dict()
        
        assert 'session_id' in session_dict
        assert 'user_id' in session_dict
        assert 'username' in session_dict
        assert 'created_at' in session_dict
        assert 'expires_at' in session_dict
        assert session_dict['username'] == "testuser"


class TestUserLogout:
    """Tests for user logout functionality."""
    
    def test_logout_success(self):
        """Test successful logout terminates session."""
        # Register and login
        AuthService.register("testuser", "password123")
        result = AuthService.login("testuser", "password123")
        
        session_id = result['session_id']
        
        # Verify session is valid before logout
        assert AuthService.validate_session(session_id) is True
        
        # Logout
        logout_result = AuthService.logout(session_id)
        
        # Verify logout was successful
        assert logout_result is True
        
        # Verify session is no longer valid
        assert AuthService.validate_session(session_id) is False
        assert AuthService.get_session(session_id) is None
    
    def test_logout_invalid_session(self):
        """Test logout with invalid session ID."""
        result = AuthService.logout("invalid-session-id")
        assert result is False
    
    def test_logout_empty_session_id(self):
        """Test logout with empty session ID."""
        result = AuthService.logout("")
        assert result is False
    
    def test_logout_already_logged_out(self):
        """Test logout with already terminated session."""
        # Register and login
        AuthService.register("testuser", "password123")
        result = AuthService.login("testuser", "password123")
        
        session_id = result['session_id']
        
        # Logout once
        AuthService.logout(session_id)
        
        # Attempt to logout again
        result = AuthService.logout(session_id)
        assert result is False
    
    def test_logout_does_not_affect_other_sessions(self):
        """Test that logging out one session doesn't affect others."""
        # Register a user
        AuthService.register("testuser", "password123")
        
        # Create two sessions
        result1 = AuthService.login("testuser", "password123")
        result2 = AuthService.login("testuser", "password123")
        
        session_id1 = result1['session_id']
        session_id2 = result2['session_id']
        
        # Logout first session
        AuthService.logout(session_id1)
        
        # Verify first session is invalid
        assert AuthService.validate_session(session_id1) is False
        
        # Verify second session is still valid
        assert AuthService.validate_session(session_id2) is True


class TestSessionCleanup:
    """Tests for session cleanup functionality."""
    
    def test_cleanup_expired_sessions(self):
        """Test cleanup removes expired sessions."""
        # Register and login
        AuthService.register("testuser", "password123")
        result1 = AuthService.login("testuser", "password123")
        result2 = AuthService.login("testuser", "password123")
        
        # Expire first session
        session1 = AuthService._sessions[result1['session_id']]
        session1.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Run cleanup
        removed_count = AuthService.cleanup_expired_sessions()
        
        # Verify one session was removed
        assert removed_count == 1
        
        # Verify expired session is gone
        assert AuthService.get_session(result1['session_id']) is None
        
        # Verify valid session still exists
        assert AuthService.get_session(result2['session_id']) is not None
    
    def test_cleanup_no_expired_sessions(self):
        """Test cleanup with no expired sessions."""
        # Register and login
        AuthService.register("testuser", "password123")
        AuthService.login("testuser", "password123")
        
        # Run cleanup
        removed_count = AuthService.cleanup_expired_sessions()
        
        # Verify no sessions were removed
        assert removed_count == 0
    
    def test_clear_all_sessions(self):
        """Test clearing all sessions."""
        # Register and create multiple sessions
        AuthService.register("testuser1", "password123")
        AuthService.register("testuser2", "password123")
        AuthService.login("testuser1", "password123")
        AuthService.login("testuser2", "password123")
        
        # Clear all sessions
        AuthService.clear_all_sessions()
        
        # Verify all sessions are gone
        assert len(AuthService._sessions) == 0


class TestIntegrationScenarios:
    """Integration tests for complete authentication workflows."""
    
    def test_complete_auth_workflow(self):
        """Test complete workflow: register -> login -> validate -> logout."""
        # Register
        register_result = AuthService.register("testuser", "password123")
        assert register_result['username'] == "testuser"
        
        # Login
        login_result = AuthService.login("testuser", "password123")
        session_id = login_result['session_id']
        assert AuthService.validate_session(session_id)
        
        # Get user from session
        user = AuthService.get_user_from_session(session_id)
        assert user.username == "testuser"
        
        # Logout
        logout_result = AuthService.logout(session_id)
        assert logout_result is True
        assert not AuthService.validate_session(session_id)
    
    def test_multiple_users_isolation(self):
        """Test that multiple users have isolated sessions."""
        # Register two users
        AuthService.register("user1", "password1")
        AuthService.register("user2", "password2")
        
        # Login both users
        result1 = AuthService.login("user1", "password1")
        result2 = AuthService.login("user2", "password2")
        
        # Verify sessions are different
        assert result1['session_id'] != result2['session_id']
        
        # Verify each session returns correct user
        user1 = AuthService.get_user_from_session(result1['session_id'])
        user2 = AuthService.get_user_from_session(result2['session_id'])
        
        assert user1.username == "user1"
        assert user2.username == "user2"
        
        # Logout user1
        AuthService.logout(result1['session_id'])
        
        # Verify user1 session is invalid but user2 is still valid
        assert not AuthService.validate_session(result1['session_id'])
        assert AuthService.validate_session(result2['session_id'])
