"""
Database connection manager and schema initialization for MoClo Library Tool.
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Optional


class Database:
    """Database connection manager with schema initialization."""
    
    def __init__(self, db_path: str):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_directory()
    
    def _ensure_directory(self):
        """Ensure the directory for the database file exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def initialize_schema(self):
        """
        Initialize database schema with all tables and indexes.
        Creates tables if they don't exist.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create parts table with extended metadata fields
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    part_type TEXT NOT NULL,
                    sequence TEXT NOT NULL,
                    overhang_5prime TEXT NOT NULL,
                    overhang_3prime TEXT NOT NULL,
                    lab_source TEXT NOT NULL,
                    contributor TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT,
                    -- Extended metadata fields (all optional)
                    plasmid_id TEXT,
                    location_80 TEXT,
                    location_96_plate TEXT,
                    antibiotic TEXT,
                    level TEXT,
                    unit TEXT,
                    donor_organism TEXT,
                    reference TEXT,
                    size INTEGER,
                    host_strain TEXT,
                    sequenced TEXT,
                    comments TEXT,
                    ori_ecoli TEXT,
                    ori_agro TEXT,
                    primer_for_seq TEXT,
                    FOREIGN KEY (contributor) REFERENCES users(username)
                )
            """)
            
            # Create cassettes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cassettes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    part_ids TEXT NOT NULL,
                    assembled_sequence TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(id)
                )
            """)
            
            # Create backbones table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backbones (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    sequence TEXT NOT NULL,
                    description TEXT,
                    genbank_data TEXT,
                    restriction_sites TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    plasmid_id TEXT,
                    location_80 TEXT,
                    location_96_plate TEXT,
                    antibiotic TEXT,
                    level TEXT,
                    unit TEXT,
                    ori_ecoli TEXT,
                    ori_agro TEXT,
                    size INTEGER,
                    host_strain TEXT,
                    primer_for_seq TEXT,
                    sequenced TEXT,
                    comments TEXT,
                    contributor TEXT,
                    donor_organism TEXT,
                    lab_source TEXT,
                    overhang_5prime TEXT,
                    overhang_3prime TEXT,
                    reference TEXT,
                    upload_date TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(id)
                )
            """)
            
            # Create final_plasmids table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS final_plasmids (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    backbone_id TEXT NOT NULL,
                    cassette_ids TEXT NOT NULL,
                    assembled_sequence TEXT NOT NULL,
                    features TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(id),
                    FOREIGN KEY (backbone_id) REFERENCES backbones(id)
                )
            """)
            
            # Create indexes for performance
            self._create_indexes(cursor)
            
            # Run migrations for existing databases
            self._run_migrations(cursor)
            
            conn.commit()
    
    def _run_migrations(self, cursor):
        """Apply incremental schema migrations for existing databases."""
        # Add is_admin column if it doesn't exist (migration for existing DBs)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass  # Column already exists

    def _create_indexes(self, cursor):
        """
        Create indexes for performance optimization.
        
        Args:
            cursor: Database cursor
        """
        # Index for parts table - part type filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_type 
            ON parts(part_type)
        """)
        
        # Index for parts table - 5' overhang compatibility checking
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_5prime 
            ON parts(overhang_5prime)
        """)
        
        # Index for parts table - 3' overhang compatibility checking
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_3prime 
            ON parts(overhang_3prime)
        """)
        
        # Index for cassettes table - owner lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cassettes_owner 
            ON cassettes(owner_id)
        """)
        
        # Index for backbones table - owner lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_backbones_owner 
            ON backbones(owner_id)
        """)
        
        # Index for final_plasmids table - owner lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_final_plasmids_owner 
            ON final_plasmids(owner_id)
        """)
        
        # Index for final_plasmids table - backbone lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_final_plasmids_backbone 
            ON final_plasmids(backbone_id)
        """)
    
    def drop_all_tables(self):
        """
        Drop all tables from the database.
        WARNING: This will delete all data!
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS final_plasmids")
            cursor.execute("DROP TABLE IF EXISTS backbones")
            cursor.execute("DROP TABLE IF EXISTS cassettes")
            cursor.execute("DROP TABLE IF EXISTS parts")
            cursor.execute("DROP TABLE IF EXISTS users")
            conn.commit()
    
    def reset_database(self):
        """
        Reset the database by dropping and recreating all tables.
        WARNING: This will delete all data!
        """
        self.drop_all_tables()
        self.initialize_schema()


# Global database instance
_db_instance: Optional[Database] = None


def get_database(db_path: Optional[str] = None) -> Database:
    """
    Get or create the global database instance.
    
    Args:
        db_path: Path to the SQLite database file. If None, uses default.
    
    Returns:
        Database: The global database instance
    """
    global _db_instance
    
    if _db_instance is None:
        if db_path is None:
            db_path = os.environ.get('DATABASE_PATH', '/data/moclo.db')
        _db_instance = Database(db_path)
    
    return _db_instance


def initialize_database(db_path: Optional[str] = None):
    """
    Initialize the database schema.
    
    Args:
        db_path: Path to the SQLite database file. If None, uses default.
    """
    db = get_database(db_path)
    db.initialize_schema()


def get_connection():
    """
    Get a database connection.
    
    Returns:
        sqlite3.Connection: Database connection
    """
    db = get_database()
    return sqlite3.connect(db.db_path)
