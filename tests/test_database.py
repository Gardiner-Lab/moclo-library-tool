"""
Unit tests for database schema and connection manager.
"""

import pytest
import os
import tempfile
from app.models.database import Database, get_database, initialize_database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    db = Database(db_path)
    db.initialize_schema()
    
    yield db
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_database_initialization(temp_db):
    """Test that database initializes with correct schema."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Check users table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        assert cursor.fetchone() is not None
        
        # Check parts table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='parts'
        """)
        assert cursor.fetchone() is not None
        
        # Check cassettes table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='cassettes'
        """)
        assert cursor.fetchone() is not None


def test_users_table_schema(temp_db):
    """Test that users table has correct columns."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert 'id' in columns
        assert 'username' in columns
        assert 'password_hash' in columns
        assert 'created_at' in columns
        assert columns['id'] == 'TEXT'
        assert columns['username'] == 'TEXT'
        assert columns['password_hash'] == 'TEXT'


def test_parts_table_schema(temp_db):
    """Test that parts table has correct columns."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(parts)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert 'id' in columns
        assert 'name' in columns
        assert 'part_type' in columns
        assert 'sequence' in columns
        assert 'overhang_5prime' in columns
        assert 'overhang_3prime' in columns
        assert 'lab_source' in columns
        assert 'contributor' in columns
        assert 'upload_date' in columns
        assert 'description' in columns


def test_cassettes_table_schema(temp_db):
    """Test that cassettes table has correct columns."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(cassettes)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert 'id' in columns
        assert 'name' in columns
        assert 'owner_id' in columns
        assert 'part_ids' in columns
        assert 'assembled_sequence' in columns
        assert 'created_at' in columns


def test_indexes_created(temp_db):
    """Test that performance indexes are created."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_%'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        
        assert 'idx_parts_type' in indexes
        assert 'idx_parts_5prime' in indexes
        assert 'idx_parts_3prime' in indexes
        assert 'idx_cassettes_owner' in indexes


def test_connection_context_manager(temp_db):
    """Test that connection context manager works correctly."""
    # Test successful transaction
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (id, username, password_hash)
            VALUES ('test-id', 'testuser', 'hash123')
        """)
    
    # Verify data was committed
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id='test-id'")
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 'testuser'


def test_connection_rollback_on_error(temp_db):
    """Test that connection rolls back on error."""
    try:
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, username, password_hash)
                VALUES ('test-id-2', 'testuser2', 'hash456')
            """)
            # Force an error
            raise ValueError("Test error")
    except ValueError:
        pass
    
    # Verify data was rolled back
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id='test-id-2'")
        result = cursor.fetchone()
        assert result is None


def test_reset_database(temp_db):
    """Test that reset_database drops and recreates tables."""
    # Insert some data
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (id, username, password_hash)
            VALUES ('test-id', 'testuser', 'hash123')
        """)
    
    # Reset database
    temp_db.reset_database()
    
    # Verify tables exist but are empty
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        assert count == 0


def test_username_unique_constraint(temp_db):
    """Test that username has unique constraint."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (id, username, password_hash)
            VALUES ('id1', 'testuser', 'hash1')
        """)
    
    # Try to insert duplicate username
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, username, password_hash)
                VALUES ('id2', 'testuser', 'hash2')
            """)


def test_foreign_key_constraint_parts(temp_db):
    """Test that parts table has foreign key to users."""
    # Note: SQLite foreign keys need to be enabled
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # First, insert a user
        cursor.execute("""
            INSERT INTO users (id, username, password_hash)
            VALUES ('user1', 'testuser', 'hash123')
        """)
        
        # Now insert part with valid contributor
        cursor.execute("""
            INSERT INTO parts (
                id, name, part_type, sequence, 
                overhang_5prime, overhang_3prime,
                lab_source, contributor
            ) VALUES (
                'part1', 'Test Part', 'Coding', 'ATCGATCGATCG',
                'ATCG', 'GCTA',
                'Test Lab', 'testuser'
            )
        """)
        
        # Verify it was inserted
        cursor.execute("SELECT name FROM parts WHERE id='part1'")
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 'Test Part'


def test_foreign_key_constraint_cassettes(temp_db):
    """Test that cassettes table has foreign key to users."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Insert a user first
        cursor.execute("""
            INSERT INTO users (id, username, password_hash)
            VALUES ('user1', 'testuser', 'hash123')
        """)
        
        # Insert cassette with valid owner_id
        cursor.execute("""
            INSERT INTO cassettes (
                id, name, owner_id, part_ids, assembled_sequence
            ) VALUES (
                'cassette1', 'Test Cassette', 'user1', '["part1"]', 'ATCGATCG'
            )
        """)
        
        # Verify it was inserted
        cursor.execute("SELECT name FROM cassettes WHERE id='cassette1'")
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 'Test Cassette'


def test_row_factory_enables_column_access(temp_db):
    """Test that row_factory allows accessing columns by name."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (id, username, password_hash)
            VALUES ('test-id', 'testuser', 'hash123')
        """)
    
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id='test-id'")
        row = cursor.fetchone()
        
        # Test column access by name
        assert row['id'] == 'test-id'
        assert row['username'] == 'testuser'
        assert row['password_hash'] == 'hash123'


def test_directory_creation():
    """Test that database directory is created if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'subdir', 'test.db')
        db = Database(db_path)
        
        # Verify directory was created
        assert os.path.exists(os.path.dirname(db_path))
        
        # Verify we can initialize the database
        db.initialize_schema()
        assert os.path.exists(db_path)
