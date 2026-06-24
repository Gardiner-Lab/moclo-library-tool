"""
Database backup service.

Creates timestamped backups of both the main and parts databases.
Triggered on user logout.
"""

import os
import shutil
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_BACKUPS = 20  # Keep the most recent N backups per database


def _backup_dir() -> str:
    path = os.environ.get('BACKUP_DIR', '/data/backups')
    os.makedirs(path, exist_ok=True)
    return path


def _prune_old_backups(prefix: str):
    """Remove oldest backups beyond MAX_BACKUPS for a given prefix."""
    backup_path = _backup_dir()
    files = sorted(
        [f for f in os.listdir(backup_path) if f.startswith(prefix)],
        reverse=True,
    )
    for old in files[MAX_BACKUPS:]:
        try:
            os.remove(os.path.join(backup_path, old))
            logger.info(f"Pruned old backup: {old}")
        except OSError as e:
            logger.warning(f"Failed to prune backup {old}: {e}")


def backup_database(db_path: str, prefix: str) -> bool:
    """
    Copy a database file to the backup directory with a timestamp.

    Returns True on success, False on failure.
    """
    if not os.path.exists(db_path):
        logger.warning(f"Database file not found, skipping backup: {db_path}")
        return False

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(_backup_dir(), f"{prefix}_{timestamp}.db")

    try:
        shutil.copy2(db_path, dest)
        logger.info(f"Backed up {db_path} -> {dest}")
        _prune_old_backups(prefix)
        return True
    except Exception as e:
        logger.error(f"Backup failed for {db_path}: {e}")
        return False


def backup_all():
    """Back up both the main database and the parts database."""
    main_db = os.environ.get('DATABASE_PATH', '/data/moclo.db')
    parts_db = os.environ.get('PARTS_DATABASE_PATH', '/data/parts.db')

    backup_database(main_db, 'moclo')
    backup_database(parts_db, 'parts')
