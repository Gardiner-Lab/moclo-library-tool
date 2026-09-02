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
                description=description,
                level=part_data.get('level')
            )
            logger.info(f"Created part '{name}' with ID {part.id}")
        except Exception as e:
            logger.error(f"Error creating part '{name}': {e}")


def _ensure_demo_backbones():
    """Seed a demo library from real MoClo Plant Parts (Addgene kit #1000000044)
    plus two generated acceptor vectors, so a fresh install shows the full
    Level 0 -> Level 1 -> Level 2 workflow with authentic sequences.
    """
    from app.models.backbone import Backbone
    from app.models.cassette import Cassette
    from app.services.part_genbank_parser_v2 import parse_part_genbank, PartGenBankError
    from app.services.assembly import create_cassette
    from app.services.restriction_sites import build_moclo_acceptor

    demo_user = User.get_by_username('demo') or User.get_by_username('admin')
    if not demo_user:
        return

    demo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'demo_data', 'plant_moclo')

    # (file, friendly name, part_type, unit) — a coherent GGAG->AATG->GCTT->CGCT chain
    curated = [
        ('pICH51277.gb', 'p35S (short)',   'NonCodingPromoter',   'Pro'),
        ('pICH85281.gb', 'pMAS',           'NonCodingPromoter',   'Pro'),
        ('pICSL12006.gb', 'pNOS',          'NonCodingPromoter',   'Pro'),
        ('pICSL80004.gb', 'tRFP (CDS)',    'Coding',              'CDS'),
        ('pICSL80007.gb', 'CDS reporter',  'Coding',              'CDS'),
        ('pICSL80014.gb', 'CDS tag',       'Coding',              'CDS'),
        ('pICH41414.gb', 't35S',           'NonCodingTerminator', 'Ter'),
    ]

    existing = {p.name for p in Part.get_all()}
    parts_by_name = {}

    def _remember(name):
        if name not in parts_by_name:
            for h in Part.search(name):
                if h.name == name:
                    parts_by_name[name] = h
                    break

    for fname, friendly, ptype, unit in curated:
        path = os.path.join(demo_dir, fname)
        if not os.path.exists(path):
            continue
        name = f'DEMO {friendly}'
        if name in existing:
            _remember(name)
            continue
        try:
            d = parse_part_genbank(open(path, encoding='utf-8').read())
            part = Part.create(
                name=name, part_type=ptype,
                sequence=d['sequence'],
                overhang_5prime=d['overhang_5prime'],
                overhang_3prime=d['overhang_3prime'],
                lab_source='Plant MoClo (Addgene #1000000044)',
                contributor=demo_user.username,
                description=f"{friendly} - MoClo Plant Parts, from {fname.replace('.gb','')}",
                plasmid_id=fname.replace('.gb', ''), unit=unit, level='0',
                features=d.get('features'),
            )
            parts_by_name[name] = part
            logger.info(f"Created demo part {name} ({d['overhang_5prime']}->{d['overhang_3prime']})")
        except (PartGenBankError, Exception) as e:  # noqa: BLE001
            logger.error(f"Demo part {fname}: {e}")

    # Positional fusion-site linkers for multigene Level 2 assembly. Real MoClo
    # supplies these through position-specific Level 1 vectors; here they are
    # short Level 0 linker parts so the demo can chain three transcription units
    # into the single-slot Level 2 acceptor: GGAG .. GTCA .. TAGC .. CGCT.
    linkers = [
        ('DEMO end-linker A (CGCT->GTCA)',   'CGCT', 'GTCA', 'CGCTAGGATCACTTGACCAATGCAGTCA'),
        ('DEMO end-linker B (CGCT->TAGC)',   'CGCT', 'TAGC', 'CGCTAGGATCACTTGACCAATGCATAGC'),
        ('DEMO start-linker B (GTCA->GGAG)', 'GTCA', 'GGAG', 'GTCATTGACCAATCACTAGGATCAGGAG'),
        ('DEMO start-linker C (TAGC->GGAG)', 'TAGC', 'GGAG', 'TAGCTTGACCAATCACTAGGATCAGGAG'),
    ]
    for name, oh5, oh3, seq in linkers:
        if name in existing:
            _remember(name)
            continue
        try:
            p = Part.create(
                name=name, part_type='NonCodingOther', sequence=seq,
                overhang_5prime=oh5, overhang_3prime=oh3,
                lab_source='Generated', contributor=demo_user.username,
                description='Positional fusion-site linker for multigene Level 2 assembly',
                unit='Linker', level='0',
            )
            parts_by_name[name] = p
            logger.info(f"Created demo linker {name} ({oh5}->{oh3})")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Demo linker {name}: {e}")

    # Acceptor vectors (generated: Plant kit acceptors are not in the parts registry)
    have_bb = {b.name for b in Backbone.get_all()}
    for name, enz, desc in [
        ('DEMO L1 acceptor (BsaI)', 'BsaI',
         'Level 1 acceptor. Accepts Level 0 parts (GGAG..CGCT) to build a transcription unit.'),
        ('DEMO L2 acceptor (BpiI)', 'BpiI',
         'Level 2 acceptor. Accepts a Level 1 cassette, or a chain of them, to build a multigene construct.'),
    ]:
        if name in have_bb:
            continue
        try:
            Backbone.create(
                name=name, owner_id=demo_user.id,
                sequence=build_moclo_acceptor('GGAG', 'CGCT', enzyme=enz),
                description=desc, restriction_sites=[],
                overhang_5prime='GGAG', overhang_3prime='CGCT',
                contributor='demo', lab_source='Generated',
            )
            logger.info(f"Created {name}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Demo backbone {name}: {e}")

    # Demo Level 1 cassettes. One plain transcription unit, plus three
    # position-linked units (TU1..TU3) whose overhangs chain GGAG -> GTCA ->
    # TAGC -> CGCT so they assemble together into the Level 2 acceptor.
    have_cas = {c.name for c in Cassette.get_all()}
    cassettes_by_name = {c.name: c for c in Cassette.get_all()}
    cassette_specs = [
        ('DEMO transcription unit',
         ['DEMO p35S (short)', 'DEMO tRFP (CDS)', 'DEMO t35S']),
        ('DEMO TU1 p35S>tRFP (GGAG..GTCA)',
         ['DEMO p35S (short)', 'DEMO tRFP (CDS)', 'DEMO t35S',
          'DEMO end-linker A (CGCT->GTCA)']),
        ('DEMO TU2 pMAS>reporter (GTCA..TAGC)',
         ['DEMO start-linker B (GTCA->GGAG)', 'DEMO pMAS', 'DEMO CDS reporter',
          'DEMO t35S', 'DEMO end-linker B (CGCT->TAGC)']),
        ('DEMO TU3 pNOS>tag (TAGC..CGCT)',
         ['DEMO start-linker C (TAGC->GGAG)', 'DEMO pNOS', 'DEMO CDS tag',
          'DEMO t35S']),
    ]
    for cname, pnames in cassette_specs:
        if cname in have_cas:
            continue
        parts = [parts_by_name.get(n) for n in pnames]
        if any(p is None for p in parts):
            missing = [n for n, p in zip(pnames, parts) if p is None]
            logger.warning(f"Demo cassette {cname}: missing parts {missing}, skipping")
            continue
        try:
            cas = create_cassette(name=cname, owner_id=demo_user.id, parts=parts)
            cassettes_by_name[cname] = cas
            logger.info(f"Created {cname} "
                        f"({cas.assembled_sequence[:4]}->{cas.assembled_sequence[-4:]})")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Demo cassette {cname}: {e}")

    # Pre-assemble the multigene Level 2 plasmid so the demo library itself
    # reaches Level 2: the three chained transcription units in the L2 acceptor.
    try:
        from app.models.final_plasmid import FinalPlasmid
        from app.services.plasmid_assembly import assemble_plasmid

        l2 = next((b for b in Backbone.get_all()
                   if b.name == 'DEMO L2 acceptor (BpiI)'), None)
        chain = [cassettes_by_name.get('DEMO TU1 p35S>tRFP (GGAG..GTCA)'),
                 cassettes_by_name.get('DEMO TU2 pMAS>reporter (GTCA..TAGC)'),
                 cassettes_by_name.get('DEMO TU3 pNOS>tag (TAGC..CGCT)')]
        done = {p.name for p in FinalPlasmid.get_all()}
        if l2 and all(chain) and 'DEMO multigene L2 (3 TUs)' not in done:
            pl = assemble_plasmid(backbone=l2, cassettes=chain,
                                  name='DEMO multigene L2 (3 TUs)',
                                  owner_id=demo_user.id)
            logger.info(f"Created DEMO multigene L2 (3 TUs), {pl.size} bp")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Demo multigene L2: {e}")


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
    
    # Only load seed data and demo content on FIRST RUN (fresh database)
    # This prevents modifying user data on container updates
    if not db_exists:
        # Load and apply seed data if provided
        if seed_file:
            seed_data = load_seed_data(seed_file)
            if seed_data:
                logger.info("Loading seed data (first run)...")
                
                # Create users first (parts reference users)
                if 'users' in seed_data:
                    logger.info(f"Creating {len(seed_data['users'])} users...")
                    create_seed_users(seed_data['users'], db_path)
                
                # Create parts (goes into the separate parts database)
                if 'parts' in seed_data:
                    logger.info(f"Creating {len(seed_data['parts'])} parts...")
                    create_seed_parts(seed_data['parts'], db_path)
                
                logger.info("Seed data loaded successfully")
        
        # Create demo data on first run
        _ensure_demo_backbones()
        logger.info("Demo data created")
    else:
        logger.info("Existing database - skipping seed/demo data (preserving user data)")
    
    # Always ensure a default admin user exists (even on updates)
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
