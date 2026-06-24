"""
Database migration script to add extended metadata fields to parts table.
"""

import sqlite3
import os


def migrate_parts_table(db_path: str):
    """
    Add extended metadata fields to the parts table.
    
    Args:
        db_path: Path to the SQLite database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List of new columns to add
    new_columns = [
        ('plasmid_id', 'TEXT'),
        ('location_80', 'TEXT'),
        ('location_96_plate', 'TEXT'),
        ('antibiotic', 'TEXT'),
        ('level', 'TEXT'),
        ('unit', 'TEXT'),
        ('donor_organism', 'TEXT'),
        ('reference', 'TEXT'),
        ('size', 'INTEGER'),
        ('host_strain', 'TEXT'),
        ('sequenced', 'TEXT'),
        ('comments', 'TEXT'),
    ]
    
    # Check which columns already exist
    cursor.execute("PRAGMA table_info(parts)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # Add missing columns
    for column_name, column_type in new_columns:
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE parts ADD COLUMN {column_name} {column_type}")
                print(f"Added column: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"Could not add column {column_name}: {e}")
    
    conn.commit()
    conn.close()
    print("Migration completed successfully!")


if __name__ == '__main__':
    # Get database path from environment or use default
    db_path = os.environ.get('DATABASE_PATH', '/data/moclo.db')
    
    if os.path.exists(db_path):
        print(f"Migrating database at: {db_path}")
        migrate_parts_table(db_path)
    else:
        print(f"Database not found at: {db_path}")
        print("No migration needed - new database will be created with updated schema")
