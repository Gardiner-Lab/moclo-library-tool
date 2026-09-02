"""
Pytest configuration and fixtures for the MoClo Library Tool tests.
"""

import os
# Prevent demo seeding as an import-time side effect (keeps the parts DB empty
# for tests that assert on it). Must be set before app.main is imported.
os.environ.setdefault("MOCLO_SKIP_SEED", "1")

import pytest
import tempfile
from app.main import create_app


@pytest.fixture(autouse=True)
def _isolate_databases(tmp_path, monkeypatch):
    """Give every test its own empty main and parts databases.

    The parts catalogue lives in a separate SQLite file behind a module-level
    singleton; without this reset, parts (including Hypothesis-generated ones)
    leak between tests and break assertions like ``Part.get_all() == []``.
    """
    import app.models.database as _main_db
    import app.models.parts_database as _parts_db

    main_path = str(tmp_path / "moclo.db")
    parts_path = str(tmp_path / "parts.db")
    monkeypatch.setenv("DATABASE_PATH", main_path)
    monkeypatch.setenv("PARTS_DATABASE_PATH", parts_path)

    _main_db._db_instance = None
    _parts_db._parts_db_instance = None
    _main_db.initialize_database(main_path)
    _parts_db.initialize_parts_database(parts_path)

    yield

    _main_db._db_instance = None
    _parts_db._parts_db_instance = None


@pytest.fixture
def app():
    """Create and configure a test Flask application instance."""
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp()
    
    # Create app with test configuration
    test_app = create_app()
    test_app.config['TESTING'] = True
    test_app.config['DATABASE_PATH'] = db_path
    test_app.config['SECRET_KEY'] = 'test-secret-key'
    
    yield test_app
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner for the Flask application."""
    return app.test_cli_runner()
