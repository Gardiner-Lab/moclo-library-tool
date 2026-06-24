"""
Pytest configuration and fixtures for the MoClo Library Tool tests.
"""

import pytest
import os
import tempfile
from app.main import create_app


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
