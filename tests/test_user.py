"""
Unit tests for User model with CRUD operations and password hashing.
"""

import pytest
import os
import tempfile
from app.models.database import Database
from app.models.user import User


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    # Set environment variable for database path
    os.environ['DATABASE_PATH'] = db_path
    
    # Import get_database after setting env var to ensure it uses our test db
    from app.models.database import get_database
    
    # Reset the global instance
    import app.models.database
    app.models.database._db_instance = None
    
    db = get_database(db_path)
    db.initialize_schema()
    
    yield db
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)
    
    # Reset global instance
    app.models.database._db_instance = None


def test_user_creation(temp_db):
    """Test creating a new user with password hashing."""
    user = User.create(username='testuser', password='password123')
    
    assert user.id is not None
    assert user.username == 'testuser'
    assert user.password_hash is not None
    assert user.password_hash != 'password123'  # Password should be hashed
    assert user.created_at is not None


def test_password_hashing(temp_db):
    """Test that passwords are properly hashed using bcrypt."""
    password = 'mySecurePassword123'
    hashed = User.hash_password(password)
    
    # Hash should be different from original password
    assert hashed != password
    
    # Hash should start with bcrypt prefix
    assert hashed.startswith('$2b$')
    
    # Hashing same password twice should produce different hashes (due to salt)
    hashed2 = User.hash_password(password)
    assert hashed != hashed2


def test_password_verification(temp_db):
    """Test password verification against hash."""
    password = 'testPassword456'
    hashed = User.hash_password(password)
    
    # Correct password should verify
    assert User.verify_password(password, hashed) is True
    
    # Incorrect password should not verify
    assert User.verify_password('wrongPassword', hashed) is False
    assert User.verify_password('testPassword457', hashed) is False


def test_user_creation_with_password_verification(temp_db):
    """Test that created user's password can be verified."""
    user = User.create(username='testuser', password='myPassword')
    
    # Verify correct password
    assert User.verify_password('myPassword', user.password_hash) is True
    
    # Verify incorrect password fails
    assert User.verify_password('wrongPassword', user.password_hash) is False


def test_duplicate_username_raises_error(temp_db):
    """Test that creating a user with duplicate username raises error."""
    User.create(username='testuser', password='password1')
    
    # Attempting to create another user with same username should raise ValueError
    with pytest.raises(ValueError, match="Username 'testuser' already exists"):
        User.create(username='testuser', password='password2')


def test_get_user_by_id(temp_db):
    """Test retrieving a user by ID."""
    created_user = User.create(username='testuser', password='password123')
    
    # Retrieve user by ID
    retrieved_user = User.get_by_id(created_user.id)
    
    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.username == created_user.username
    assert retrieved_user.password_hash == created_user.password_hash


def test_get_user_by_id_not_found(temp_db):
    """Test that get_by_id returns None for non-existent user."""
    user = User.get_by_id('non-existent-id')
    assert user is None


def test_get_user_by_username(temp_db):
    """Test retrieving a user by username."""
    created_user = User.create(username='testuser', password='password123')
    
    # Retrieve user by username
    retrieved_user = User.get_by_username('testuser')
    
    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.username == created_user.username
    assert retrieved_user.password_hash == created_user.password_hash


def test_get_user_by_username_not_found(temp_db):
    """Test that get_by_username returns None for non-existent user."""
    user = User.get_by_username('nonexistent')
    assert user is None


def test_update_username(temp_db):
    """Test updating a user's username."""
    user = User.create(username='oldusername', password='password123')
    original_id = user.id
    
    # Update username
    user.update(username='newusername')
    
    assert user.username == 'newusername'
    assert user.id == original_id  # ID should not change
    
    # Verify in database
    retrieved_user = User.get_by_id(user.id)
    assert retrieved_user.username == 'newusername'
    
    # Old username should not exist
    assert User.get_by_username('oldusername') is None


def test_update_username_duplicate_raises_error(temp_db):
    """Test that updating to an existing username raises error."""
    user1 = User.create(username='user1', password='password1')
    user2 = User.create(username='user2', password='password2')
    
    # Attempting to update user2's username to user1 should raise error
    with pytest.raises(ValueError, match="Username 'user1' already exists"):
        user2.update(username='user1')


def test_update_password(temp_db):
    """Test updating a user's password."""
    user = User.create(username='testuser', password='oldPassword')
    old_hash = user.password_hash
    
    # Update password
    user.update(password='newPassword')
    
    # Password hash should change
    assert user.password_hash != old_hash
    
    # Old password should not work
    assert User.verify_password('oldPassword', user.password_hash) is False
    
    # New password should work
    assert User.verify_password('newPassword', user.password_hash) is True
    
    # Verify in database
    retrieved_user = User.get_by_id(user.id)
    assert User.verify_password('newPassword', retrieved_user.password_hash) is True


def test_update_both_username_and_password(temp_db):
    """Test updating both username and password simultaneously."""
    user = User.create(username='olduser', password='oldPassword')
    
    user.update(username='newuser', password='newPassword')
    
    assert user.username == 'newuser'
    assert User.verify_password('newPassword', user.password_hash) is True
    assert User.verify_password('oldPassword', user.password_hash) is False


def test_delete_user(temp_db):
    """Test deleting a user."""
    user = User.create(username='testuser', password='password123')
    user_id = user.id
    
    # Delete user
    user.delete()
    
    # User should no longer exist
    assert User.get_by_id(user_id) is None
    assert User.get_by_username('testuser') is None


def test_get_all_users(temp_db):
    """Test retrieving all users."""
    # Create multiple users
    user1 = User.create(username='user1', password='password1')
    user2 = User.create(username='user2', password='password2')
    user3 = User.create(username='user3', password='password3')
    
    # Get all users
    all_users = User.get_all()
    
    assert len(all_users) == 3
    
    # Check that all created users are in the list
    usernames = [u.username for u in all_users]
    assert 'user1' in usernames
    assert 'user2' in usernames
    assert 'user3' in usernames


def test_get_all_users_empty(temp_db):
    """Test get_all returns empty list when no users exist."""
    users = User.get_all()
    assert users == []


def test_user_to_dict(temp_db):
    """Test converting user to dictionary (excluding password_hash)."""
    user = User.create(username='testuser', password='password123')
    user_dict = user.to_dict()
    
    assert 'id' in user_dict
    assert 'username' in user_dict
    assert 'created_at' in user_dict
    assert 'password_hash' not in user_dict  # Should not expose password hash
    
    assert user_dict['id'] == user.id
    assert user_dict['username'] == user.username


def test_user_repr(temp_db):
    """Test user string representation."""
    user = User.create(username='testuser', password='password123')
    repr_str = repr(user)
    
    assert 'User' in repr_str
    assert user.id in repr_str
    assert 'testuser' in repr_str


def test_user_equality(temp_db):
    """Test user equality based on ID."""
    user1 = User.create(username='user1', password='password1')
    user2 = User.create(username='user2', password='password2')
    
    # Same user retrieved twice should be equal
    user1_copy = User.get_by_id(user1.id)
    assert user1 == user1_copy
    
    # Different users should not be equal
    assert user1 != user2
    
    # User should not equal non-User object
    assert user1 != "not a user"
    assert user1 != None


def test_user_created_at_timestamp(temp_db):
    """Test that created_at timestamp is set automatically."""
    user = User.create(username='testuser', password='password123')
    
    assert user.created_at is not None
    # Timestamp should be in ISO format (contains date and time)
    assert '-' in user.created_at  # Date separator
    assert ':' in user.created_at  # Time separator


def test_multiple_users_different_ids(temp_db):
    """Test that each user gets a unique ID."""
    user1 = User.create(username='user1', password='password1')
    user2 = User.create(username='user2', password='password2')
    user3 = User.create(username='user3', password='password3')
    
    # All IDs should be unique
    ids = [user1.id, user2.id, user3.id]
    assert len(ids) == len(set(ids))  # No duplicates


def test_password_hash_stored_as_string(temp_db):
    """Test that password hash is stored as string in database."""
    user = User.create(username='testuser', password='password123')
    
    # Retrieve directly from database
    from app.models.database import get_database
    db = get_database()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,))
        row = cursor.fetchone()
        
        assert isinstance(row['password_hash'], str)
        assert row['password_hash'].startswith('$2b$')


def test_update_with_no_changes(temp_db):
    """Test that update with no parameters doesn't cause errors."""
    user = User.create(username='testuser', password='password123')
    original_username = user.username
    original_hash = user.password_hash
    
    # Update with no changes
    user.update()
    
    # Nothing should change
    assert user.username == original_username
    assert user.password_hash == original_hash


def test_update_username_to_same_value(temp_db):
    """Test that updating username to same value works."""
    user = User.create(username='testuser', password='password123')
    
    # Update to same username should work
    user.update(username='testuser')
    
    assert user.username == 'testuser'
