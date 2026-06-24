"""
User model with CRUD operations and password hashing.
"""

import uuid
import bcrypt
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.database import get_database


class User:
    """User model representing an authenticated user in the system."""
    
    def __init__(
        self,
        id: str,
        username: str,
        password_hash: str,
        created_at: Optional[str] = None,
        is_admin: bool = False
    ):
        """
        Initialize a User instance.
        
        Args:
            id: Unique identifier (UUID)
            username: Unique username
            password_hash: Bcrypt hashed password
            created_at: Timestamp of user creation (ISO format)
            is_admin: Whether this user has admin privileges
        """
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.created_at = created_at
        self.is_admin = bool(is_admin)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert user to dictionary representation.
        
        Returns:
            Dictionary with user data (excluding password_hash)
        """
        return {
            'id': self.id,
            'username': self.username,
            'created_at': self.created_at,
            'is_admin': self.is_admin
        }
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Bcrypt hashed password as string
        """
        # Generate salt and hash password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify a password against a hash.
        
        Args:
            password: Plain text password to verify
            password_hash: Bcrypt hashed password
            
        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )
    
    @staticmethod
    def create(username: str, password: str, is_admin: bool = False) -> 'User':
        """
        Create a new user with hashed password.
        
        Args:
            username: Unique username
            password: Plain text password
            is_admin: Whether this user has admin privileges
            
        Returns:
            Created User instance
            
        Raises:
            ValueError: If username already exists
            sqlite3.IntegrityError: If database constraint is violated
        """
        # Generate unique ID
        user_id = str(uuid.uuid4())
        
        # Hash password
        password_hash = User.hash_password(password)
        
        # Insert into database
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if username already exists
            cursor.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,)
            )
            if cursor.fetchone() is not None:
                raise ValueError(f"Username '{username}' already exists")
            
            # Insert new user
            cursor.execute(
                """
                INSERT INTO users (id, username, password_hash, is_admin)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, username, password_hash, 1 if is_admin else 0)
            )
            
            # Retrieve the created user
            cursor.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            
            return User(
                id=row['id'],
                username=row['username'],
                password_hash=row['password_hash'],
                created_at=row['created_at'],
                is_admin=bool(row['is_admin']) if 'is_admin' in row.keys() else False
            )
    
    @staticmethod
    def get_by_id(user_id: str) -> Optional['User']:
        """
        Retrieve a user by ID.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            User instance if found, None otherwise
        """
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return User(
                id=row['id'],
                username=row['username'],
                password_hash=row['password_hash'],
                created_at=row['created_at'],
                is_admin=bool(row['is_admin']) if 'is_admin' in row.keys() else False
            )
    
    @staticmethod
    def get_by_username(username: str) -> Optional['User']:
        """
        Retrieve a user by username.
        
        Args:
            username: Username to look up
            
        Returns:
            User instance if found, None otherwise
        """
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return User(
                id=row['id'],
                username=row['username'],
                password_hash=row['password_hash'],
                created_at=row['created_at'],
                is_admin=bool(row['is_admin']) if 'is_admin' in row.keys() else False
            )
    
    def update(self, username: Optional[str] = None, password: Optional[str] = None, is_admin: Optional[bool] = None) -> None:
        """
        Update user information.
        
        Args:
            username: New username (optional)
            password: New plain text password (optional)
            is_admin: New admin status (optional)
            
        Raises:
            ValueError: If username already exists
        """
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Update username if provided
            if username is not None and username != self.username:
                # Check if new username already exists
                cursor.execute(
                    "SELECT id FROM users WHERE username = ? AND id != ?",
                    (username, self.id)
                )
                if cursor.fetchone() is not None:
                    raise ValueError(f"Username '{username}' already exists")
                
                cursor.execute(
                    "UPDATE users SET username = ? WHERE id = ?",
                    (username, self.id)
                )
                self.username = username
            
            # Update password if provided
            if password is not None:
                password_hash = User.hash_password(password)
                cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (password_hash, self.id)
                )
                self.password_hash = password_hash
            
            # Update admin status if provided
            if is_admin is not None:
                cursor.execute(
                    "UPDATE users SET is_admin = ? WHERE id = ?",
                    (1 if is_admin else 0, self.id)
                )
                self.is_admin = is_admin
    
    def delete(self) -> None:
        """
        Delete this user from the database.
        
        Note: This will fail if there are cassettes or parts referencing this user
        due to foreign key constraints.
        """
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM users WHERE id = ?",
                (self.id,)
            )
    
    @staticmethod
    def get_all() -> list['User']:
        """
        Retrieve all users from the database.
        
        Returns:
            List of User instances
        """
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
            rows = cursor.fetchall()
            
            return [
                User(
                    id=row['id'],
                    username=row['username'],
                    password_hash=row['password_hash'],
                    created_at=row['created_at'],
                    is_admin=bool(row['is_admin']) if 'is_admin' in row.keys() else False
                )
                for row in rows
            ]
    
    def __repr__(self) -> str:
        """String representation of User."""
        return f"User(id='{self.id}', username='{self.username}')"
    
    def __eq__(self, other) -> bool:
        """Check equality based on user ID."""
        if not isinstance(other, User):
            return False
        return self.id == other.id
