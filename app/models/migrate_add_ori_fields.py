"""
Migration script to add ori_ecoli, ori_agro, and primer_for_seq fields to parts table.
"""

import sqlite3
import os

def migrate():
    """Add new fields to parts table."""
    db_path = os.environ.get('DATABASE_PATH', '/data/moclo.db')
    
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Adding new fields to parts table...")
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(parts)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    fields_to_add = [
        ('ori_ecoli', 'TEXT'),
        ('ori_agro', 'TEXT'),
        ('primer_for_seq', 'TEXT')
    ]
    
    added_count = 0
    for field_name, field_type in fields_to_add:
        if field_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE parts ADD COLUMN {field_name} {field_type}")
                print(f"✓ Added column: {field_name}")
                added_count += 1
            except Exception as e:
                print(f"✗ Failed to add {field_name}: {e}")
        else:
            print(f"  Column {field_name} already exists")
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Migration complete! Added {added_count} new columns")
    return True

if __name__ == '__main__':
    migrate()
