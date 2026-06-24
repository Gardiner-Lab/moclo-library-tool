"""
Database initialization script for MoClo Library Tool.

This script initializes the database on first run and optionally loads seed data.
It can be run standalone or imported and called from the main application.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import get_database, initialize_database
from app.models.parts_database import get_parts_database, initialize_parts_database
from app.models.user import User
from app.models.part import Part

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_database_exists(db_path: str) -> bool:
    """
    Check if the database file exists and has tables.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        bool: True if database exists and has tables, False otherwise
    """
    if not os.path.exists(db_path):
        return False
    
    try:
        db = get_database(db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            result = cursor.fetchone()
            return result is not None
    except Exception as e:
        logger.warning(f"Error checking database: {e}")
        return False


def load_seed_data(seed_file: str) -> Optional[Dict[str, List[Any]]]:
    """
    Load seed data from a JSON file.
    
    Expected format:
    {
        "users": [
            {"username": "admin", "password": "admin123"},
            ...
        ],
        "parts": [
            {
                "name": "Part1",
                "part_type": "Coding",
                "sequence": "ATCGATCGATCG",
                "overhang_5prime": "ATCG",
                "overhang_3prime": "GCTA",
                "lab_source": "Lab A",
                "contributor": "admin",
                "description": "Test part"
            },
            ...
        ]
    }
    
    Args:
        seed_file: Path to the seed data JSON file
        
    Returns:
        Dict containing seed data, or None if file doesn't exist or is invalid
    """
    if not os.path.exists(seed_file):
        logger.info(f"No seed data file found at {seed_file}")
        return None
    
    try:
        with open(seed_file, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded seed data from {seed_file}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in seed file {seed_file}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading seed file {seed_file}: {e}")
        return None


def create_seed_users(users_data: List[Dict[str, str]], db_path: str) -> Dict[str, str]:
    """
    Create users from seed data.
    
    Args:
        users_data: List of user dictionaries with username and password
        db_path: Path to the database
        
    Returns:
        Dict mapping usernames to user IDs
    """
    user_ids = {}
    
    for user_data in users_data:
        username = user_data.get('username')
        password = user_data.get('password')
        
        if not username or not password:
            logger.warning(f"Skipping invalid user data: {user_data}")
            continue
        
        try:
            # Check if user already exists
            existing_user = User.get_by_username(username)
            if existing_user:
                logger.info(f"User '{username}' already exists, skipping")
                user_ids[username] = existing_user.id
                continue
            
            # Create new user
            is_admin = bool(user_data.get('is_admin', False))
            user = User.create(username, password, is_admin=is_admin)
            user_ids[username] = user.id
            logger.info(f"Created user '{username}' (admin={is_admin}) with ID {user.id}")
        except Exception as e:
            logger.error(f"Error creating user '{username}': {e}")
    
    return user_ids
    
    return user_ids


def create_seed_parts(parts_data: List[Dict[str, str]], db_path: str):
    """
    Create parts from seed data.
    
    Args:
        parts_data: List of part dictionaries
        db_path: Path to the database
    """
    for part_data in parts_data:
        name = part_data.get('name')
        part_type = part_data.get('part_type')
        sequence = part_data.get('sequence')
        overhang_5prime = part_data.get('overhang_5prime')
        overhang_3prime = part_data.get('overhang_3prime')
        lab_source = part_data.get('lab_source')
        contributor = part_data.get('contributor')
        description = part_data.get('description', '')
        
        # Validate required fields
        if not all([name, part_type, sequence, overhang_5prime, overhang_3prime, 
                   lab_source, contributor]):
            logger.warning(f"Skipping invalid part data: {part_data}")
            continue
        
        try:
            # Check if part already exists (by name)
            existing_parts = Part.search(name)
            if any(p.name == name for p in existing_parts):
                logger.info(f"Part '{name}' already exists, skipping")
                continue
            
            # Create new part
            part = Part.create(
                name=name,
                part_type=part_type,
                sequence=sequence,
                overhang_5prime=overhang_5prime,
                overhang_3prime=overhang_3prime,
                lab_source=lab_source,
                contributor=contributor,
                description=description
            )
            logger.info(f"Created part '{name}' with ID {part.id}")
        except Exception as e:
            logger.error(f"Error creating part '{name}': {e}")


def _ensure_default_admin():
    """
    Ensure a default admin user exists on every startup.
    
    Creates an 'admin' user with password 'admin123' if no admin user exists.
    This guarantees the application is always accessible after deployment.
    The password should be changed after first login.
    """
    try:
        existing_admin = User.get_by_username('admin')
        if existing_admin:
            logger.info("Admin user already exists")
            return
        
        User.create('admin', 'admin123', is_admin=True)
        logger.info("Created default admin user (username: admin, password: admin123)")
    except Exception as e:
        logger.warning(f"Could not create default admin user: {e}")


def initialize_with_seed_data(db_path: str, seed_file: Optional[str] = None):
    """
    Initialize the database and optionally load seed data.
    
    Args:
        db_path: Path to the database file
        seed_file: Optional path to seed data JSON file
    """
    logger.info("Starting database initialization...")
    
    # Check if database already exists
    db_exists = check_database_exists(db_path)
    
    if db_exists:
        logger.info(f"Database already exists at {db_path}")
        # Still run initialization to apply any pending migrations
        initialize_database(db_path)
        logger.info("Database migrations applied")
    else:
        logger.info(f"Creating new database at {db_path}")
        initialize_database(db_path)
        logger.info("Database schema created successfully")
    
    # Initialize the separate parts database
    import os
    parts_db_path = os.environ.get('PARTS_DATABASE_PATH', '/data/parts.db')
    logger.info(f"Initializing parts database at {parts_db_path}")
    initialize_parts_database(parts_db_path)
    logger.info("Parts database schema ready")
    
    # Load and apply seed data if provided
    if seed_file:
        seed_data = load_seed_data(seed_file)
        if seed_data:
            logger.info("Loading seed data...")
            
            # Create users first (parts reference users)
            if 'users' in seed_data:
                logger.info(f"Creating {len(seed_data['users'])} users...")
                create_seed_users(seed_data['users'], db_path)
            
            # Create parts (goes into the separate parts database)
            if 'parts' in seed_data:
                logger.info(f"Creating {len(seed_data['parts'])} parts...")
                create_seed_parts(seed_data['parts'], db_path)
            
            logger.info("Seed data loaded successfully")
        else:
            logger.info("No seed data to load")
    else:
        logger.info("No seed file specified, skipping seed data")
    
    # Always ensure a default admin user exists
    _ensure_default_admin()
    
    logger.info("Database initialization complete")


def main():
    """
    Main entry point for standalone script execution.
    
    Usage:
        python app/init_db.py [db_path] [seed_file]
        
    Arguments:
        db_path: Optional path to database file (default: /data/moclo.db)
        seed_file: Optional path to seed data JSON file
    """
    # Get database path from command line or environment
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('DATABASE_PATH', '/data/moclo.db')
    
    # Get seed file path from command line or environment
    seed_file = None
    if len(sys.argv) > 2:
        seed_file = sys.argv[2]
    elif os.environ.get('SEED_DATA_FILE'):
        seed_file = os.environ.get('SEED_DATA_FILE')
    elif os.path.exists('/data/seed_data.json'):
        seed_file = '/data/seed_data.json'
    
    try:
        initialize_with_seed_data(db_path, seed_file)
        logger.info("✓ Initialization completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"✗ Initialization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
