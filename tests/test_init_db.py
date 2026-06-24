"""
Tests for database initialization script.
"""

import os
import json
import tempfile
import pytest
from app.init_db import (
    check_database_exists,
    load_seed_data,
    initialize_with_seed_data
)
from app.models.user import User
from app.models.part import Part
from app.models.database import get_database


class TestDatabaseInitialization:
    """Test database initialization functionality."""
    
    def test_check_database_exists_false_for_nonexistent(self):
        """Test that check_database_exists returns False for non-existent database."""
        result = check_database_exists('/tmp/nonexistent_db.db')
        assert result is False
    
    def test_check_database_exists_true_after_creation(self):
        """Test that check_database_exists returns True after database creation."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Initialize database
            initialize_with_seed_data(db_path, None)
            
            # Check it exists
            result = check_database_exists(db_path)
            assert result is True
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_load_seed_data_returns_none_for_nonexistent_file(self):
        """Test that load_seed_data returns None for non-existent file."""
        result = load_seed_data('/tmp/nonexistent_seed.json')
        assert result is None
    
    def test_load_seed_data_returns_data_for_valid_file(self):
        """Test that load_seed_data returns data for valid JSON file."""
        seed_data = {
            'users': [{'username': 'test', 'password': 'test123'}],
            'parts': []
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(seed_data, f)
            seed_file = f.name
        
        try:
            result = load_seed_data(seed_file)
            assert result is not None
            assert 'users' in result
            assert len(result['users']) == 1
            assert result['users'][0]['username'] == 'test'
        finally:
            if os.path.exists(seed_file):
                os.unlink(seed_file)
    
    def test_load_seed_data_returns_none_for_invalid_json(self):
        """Test that load_seed_data returns None for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json {')
            seed_file = f.name
        
        try:
            result = load_seed_data(seed_file)
            assert result is None
        finally:
            if os.path.exists(seed_file):
                os.unlink(seed_file)
    
    def test_initialize_with_seed_data_creates_database(self):
        """Test that initialize_with_seed_data creates a new database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Remove the file so we start fresh
        os.unlink(db_path)
        
        try:
            # Reset global database instance
            import app.models.database as db_module
            db_module._db_instance = None
            
            # Initialize without seed data
            initialize_with_seed_data(db_path, None)
            
            # Set the global database instance to the test database
            db_module._db_instance = get_database(db_path)
            
            # Verify database exists and has tables
            assert check_database_exists(db_path)
        finally:
            # Reset global instance
            import app.models.database as db_module
            db_module._db_instance = None
            
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_initialize_with_seed_data_loads_users(self):
        """Test that initialize_with_seed_data loads users from seed data."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        seed_data = {
            'users': [
                {'username': 'user1', 'password': 'pass1'},
                {'username': 'user2', 'password': 'pass2'}
            ],
            'parts': []
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(seed_data, f)
            seed_file = f.name
        
        try:
            # Reset global database instance
            import app.models.database as db_module
            db_module._db_instance = None
            
            # Initialize with seed data
            initialize_with_seed_data(db_path, seed_file)
            
            # Set the global database instance to the test database
            db_module._db_instance = get_database(db_path)
            
            # Verify users were created
            user1 = User.get_by_username('user1')
            user2 = User.get_by_username('user2')
            
            assert user1 is not None
            assert user1.username == 'user1'
            assert user2 is not None
            assert user2.username == 'user2'
        finally:
            # Reset global instance
            import app.models.database as db_module
            db_module._db_instance = None
            
            if os.path.exists(db_path):
                os.unlink(db_path)
            if os.path.exists(seed_file):
                os.unlink(seed_file)
    
    def test_initialize_with_seed_data_loads_parts(self):
        """Test that initialize_with_seed_data loads parts from seed data."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        seed_data = {
            'users': [
                {'username': 'testuser', 'password': 'pass123'}
            ],
            'parts': [
                {
                    'name': 'TestPart1',
                    'part_type': 'Coding',
                    'sequence': 'ATCGATCGATCG',
                    'overhang_5prime': 'ATCG',
                    'overhang_3prime': 'GCTA',
                    'lab_source': 'Test Lab',
                    'contributor': 'testuser',
                    'description': 'Test part'
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(seed_data, f)
            seed_file = f.name
        
        try:
            # Reset global database instance
            import app.models.database as db_module
            db_module._db_instance = None
            
            # Initialize with seed data
            initialize_with_seed_data(db_path, seed_file)
            
            # Set the global database instance to the test database
            db_module._db_instance = get_database(db_path)
            
            # Verify parts were created
            parts = Part.search('TestPart1')
            
            assert len(parts) > 0
            part = parts[0]
            assert part.name == 'TestPart1'
            assert part.part_type == 'Coding'
            assert part.sequence == 'ATCGATCGATCG'
        finally:
            # Reset global instance
            import app.models.database as db_module
            db_module._db_instance = None
            
            if os.path.exists(db_path):
                os.unlink(db_path)
            if os.path.exists(seed_file):
                os.unlink(seed_file)
    
    def test_initialize_is_idempotent(self):
        """Test that initialization can be run multiple times safely."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        seed_data = {
            'users': [{'username': 'testuser', 'password': 'pass123'}],
            'parts': []
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(seed_data, f)
            seed_file = f.name
        
        try:
            # Reset global database instance
            import app.models.database as db_module
            db_module._db_instance = None
            
            # Initialize twice
            initialize_with_seed_data(db_path, seed_file)
            initialize_with_seed_data(db_path, seed_file)
            
            # Set the global database instance to the test database
            db_module._db_instance = get_database(db_path)
            
            # Verify only one user was created
            all_users = User.get_all()
            assert len(all_users) == 1
            assert all_users[0].username == 'testuser'
        finally:
            # Reset global instance
            import app.models.database as db_module
            db_module._db_instance = None
            
            if os.path.exists(db_path):
                os.unlink(db_path)
            if os.path.exists(seed_file):
                os.unlink(seed_file)
