"""
Separate database manager for the parts catalog.

Parts are stored in their own database file so they are never lost
when the main user/session database is reset or deleted.
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Optional


class PartsDatabase:
    """Database connection manager for the parts-only database."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_directory()

    def _ensure_directory(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self):
        """Create the parts table if it doesn't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
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
                    features TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_parts_type ON parts(part_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_parts_5prime ON parts(overhang_5prime)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_parts_3prime ON parts(overhang_3prime)
            """)
            
            # Migration: add features column to existing databases
            try:
                cursor.execute("ALTER TABLE parts ADD COLUMN features TEXT")
            except Exception:
                pass  # Column already exists
            
            conn.commit()


# Global parts database instance
_parts_db_instance: Optional[PartsDatabase] = None


def get_parts_database(db_path: Optional[str] = None) -> PartsDatabase:
    """Get or create the global parts database instance."""
    global _parts_db_instance

    if _parts_db_instance is None:
        if db_path is None:
            db_path = os.environ.get('PARTS_DATABASE_PATH', '/data/parts.db')
        _parts_db_instance = PartsDatabase(db_path)

    return _parts_db_instance


def initialize_parts_database(db_path: Optional[str] = None):
    """Initialize the parts database schema."""
    db = get_parts_database(db_path)
    db.initialize_schema()
