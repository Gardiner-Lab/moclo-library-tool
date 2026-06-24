"""
Authentication service for user registration, login, session management, and logout.

This service handles:
- User registration with password hashing
- Login with credential validation
- Session creation and management
- Logout with session termination

Requirements: 9.1, 9.2, 9.3, 9.4, 9.6
"""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from app.models.user import User


class Session:
    """Represents an active user session."""
    
    def __init__(
        self,
        session_id: str,
        user_id: str,
        username: str,
        created_at: datetime,
        expires_at: datetime
    ):
        """
        Initialize a Session instance.
        
        Args:
            session_id: Unique session identifier
            user_id: ID of the authenticated user
            username: Username of the authenticated user
            created_at: Timestamp when session was created
            expires_at: Timestamp when session expires
        """
        self.session_id = session_id
        self.user_id = user_id
        self.username = username
        self.created_at = created_at
        self.expires_at = expires_at
    
    def is_expired(self) -> bool:
        """
        Check if the session has expired.
        
        Returns:
            True if session is expired, False otherwise
        """
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert session to dictionary representation.
        
        Returns:
            Dictionary with session data
        """
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'username': self.username,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat()
        }


class AuthService:
    """
    Authentication service for managing user authentication and sessions.
    
    This service provides methods for:
    - User registration
    - User login with credential validation
    - Session management
    - User logout
    """
    
    # In-memory session storage (in production, use Redis or database)
    _sessions: Dict[str, Session] = {}
    
    # Session timeout in hours
    SESSION_TIMEOUT_HOURS = 24
    
    @classmethod
    def register(cls, username: str, password: str) -> Dict[str, Any]:
        """
        Register a new user with password hashing.
        
        Args:
            username: Desired username (must be unique)
            password: Plain text password
            
        Returns:
            Dictionary with user data (excluding password)
            
        Raises:
            ValueError: If username is empty, password is empty, or username already exists
        
        Requirements: 9.2
        """
        # Validate inputs
        if not username or not username.strip():
            raise ValueError("Username cannot be empty")
        
        if not password or not password.strip():
            raise ValueError("Password cannot be empty")
        
        # Create user (this will hash the password and check for duplicates)
        try:
            user = User.create(username.strip(), password)
            return user.to_dict()
        except ValueError as e:
            # Re-raise ValueError from User.create (e.g., username already exists)
            raise e
    
    @classmethod
    def login(cls, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user and create a session.
        
        Args:
            username: Username to authenticate
            password: Plain text password to verify
            
        Returns:
            Dictionary with session data including session_id and user info
            
        Raises:
            ValueError: If credentials are invalid
        
        Requirements: 9.3, 9.4
        """
        # Validate inputs
        if not username or not password:
            raise ValueError("Invalid username or password")
        
        # Retrieve user by username
        user = User.get_by_username(username)
        
        if user is None:
            raise ValueError("Invalid username or password")
        
        # Verify password
        if not User.verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password")
        
        # Create session
        session = cls._create_session(user)
        
        return {
            'session_id': session.session_id,
            'user': user.to_dict(),
            'expires_at': session.expires_at.isoformat()
        }
    
    @classmethod
    def _create_session(cls, user: User) -> Session:
        """
        Create a new session for an authenticated user.
        
        Args:
            user: Authenticated User instance
            
        Returns:
            Created Session instance
        
        Requirements: 9.4
        """
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Calculate expiration time
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(hours=cls.SESSION_TIMEOUT_HOURS)
        
        # Create session
        session = Session(
            session_id=session_id,
            user_id=user.id,
            username=user.username,
            created_at=created_at,
            expires_at=expires_at
        )
        
        # Store session
        cls._sessions[session_id] = session
        
        return session
    
    @classmethod
    def get_session(cls, session_id: str) -> Optional[Session]:
        """
        Retrieve a session by ID.
        
        Args:
            session_id: Session ID to look up
            
        Returns:
            Session instance if found and not expired, None otherwise
        
        Requirements: 9.4
        """
        if not session_id:
            return None
        
        session = cls._sessions.get(session_id)
        
        if session is None:
            return None
        
        # Check if session is expired
        if session.is_expired():
            # Remove expired session
            cls._sessions.pop(session_id, None)
            return None
        
        return session
    
    @classmethod
    def validate_session(cls, session_id: str) -> bool:
        """
        Validate if a session is active and not expired.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            True if session is valid, False otherwise
        
        Requirements: 9.4
        """
        session = cls.get_session(session_id)
        return session is not None
    
    @classmethod
    def get_user_from_session(cls, session_id: str) -> Optional[User]:
        """
        Get the user associated with a session.
        
        Args:
            session_id: Session ID to look up
            
        Returns:
            User instance if session is valid, None otherwise
        
        Requirements: 9.4
        """
        session = cls.get_session(session_id)
        
        if session is None:
            return None
        
        # Retrieve user from database
        return User.get_by_id(session.user_id)
    
    @classmethod
    def logout(cls, session_id: str) -> bool:
        """
        Terminate a user session (logout).
        
        Args:
            session_id: Session ID to terminate
            
        Returns:
            True if session was terminated, False if session didn't exist
        
        Requirements: 9.6
        """
        if not session_id:
            return False
        
        # Remove session from storage
        session = cls._sessions.pop(session_id, None)
        
        return session is not None
    
    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        """
        Remove all expired sessions from storage.
        
        Returns:
            Number of sessions removed
        """
        expired_session_ids = [
            session_id
            for session_id, session in cls._sessions.items()
            if session.is_expired()
        ]
        
        for session_id in expired_session_ids:
            cls._sessions.pop(session_id, None)
        
        return len(expired_session_ids)
    
    @classmethod
    def clear_all_sessions(cls) -> None:
        """
        Clear all sessions (useful for testing).
        """
        cls._sessions.clear()
