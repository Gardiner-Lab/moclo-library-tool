"""
Unit tests for Cassette model with CRUD operations and user association.
"""

import pytest
import os
import tempfile
from app.models.database import Database
from app.models.user import User
from app.models.part import Part
from app.models.cassette import Cassette


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    # Set environment variable for database path
    os.environ['DATABASE_PATH'] = db_path
    
    # Import get_database after setting env var to ensure it uses our test db
    from app.models.database import get_database
    
    # Reset the global instance
    import app.models.database
    app.models.database._db_instance = None
    
    db = get_database(db_path)
    db.initialize_schema()
    
    yield db
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)
    
    # Reset global instance
    app.models.database._db_instance = None


@pytest.fixture
def sample_user(temp_db):
    """Create a sample user for testing."""
    return User.create(username='testuser', password='password123')


@pytest.fixture
def sample_parts(temp_db, sample_user):
    """Create sample parts for testing cassette assembly."""
    part1 = Part.create(
        name='Promoter Part',
        part_type='NonCodingPromoter',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Coding Part',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part3 = Part.create(
        name='Terminator Part',
        part_type='NonCodingTerminator',
        sequence='TTAACGATCGAT',
        overhang_5prime='TTAA',
        overhang_3prime='CGTA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    return [part1, part2, part3]


def test_cassette_creation(temp_db, sample_user, sample_parts):
    """Test creating a new cassette."""
    part_ids = [p.id for p in sample_parts]
    assembled_seq = 'ATCGATCGATCGCGATCGATTTAACGATCGAT'
    
    cassette = Cassette.create(
        name='Test Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence=assembled_seq
    )
    
    assert cassette.id is not None
    assert cassette.name == 'Test Cassette'
    assert cassette.owner_id == sample_user.id
    assert cassette.part_ids == part_ids
    assert cassette.assembled_sequence == assembled_seq
    assert cassette.created_at is not None


def test_cassette_creation_validates_name(temp_db, sample_user, sample_parts):
    """Test that cassette creation validates name is not empty."""
    part_ids = [p.id for p in sample_parts]
    
    with pytest.raises(ValueError, match="Cassette name cannot be empty"):
        Cassette.create(
            name='',
            owner_id=sample_user.id,
            part_ids=part_ids,
            assembled_sequence='ATCGATCG'
        )
    
    with pytest.raises(ValueError, match="Cassette name cannot be empty"):
        Cassette.create(
            name='   ',
            owner_id=sample_user.id,
            part_ids=part_ids,
            assembled_sequence='ATCGATCG'
        )


def test_cassette_creation_validates_owner_id(temp_db, sample_parts):
    """Test that cassette creation validates owner_id is not empty."""
    part_ids = [p.id for p in sample_parts]
    
    with pytest.raises(ValueError, match="Owner ID cannot be empty"):
        Cassette.create(
            name='Test Cassette',
            owner_id='',
            part_ids=part_ids,
            assembled_sequence='ATCGATCG'
        )


def test_cassette_creation_validates_minimum_parts(temp_db, sample_user, sample_parts):
    """Test that cassette creation requires at least 2 parts."""
    # Empty list
    with pytest.raises(ValueError, match="Cassette must contain at least 2 parts"):
        Cassette.create(
            name='Test Cassette',
            owner_id=sample_user.id,
            part_ids=[],
            assembled_sequence='ATCGATCG'
        )
    
    # Single part
    with pytest.raises(ValueError, match="Cassette must contain at least 2 parts"):
        Cassette.create(
            name='Test Cassette',
            owner_id=sample_user.id,
            part_ids=[sample_parts[0].id],
            assembled_sequence='ATCGATCG'
        )


def test_cassette_creation_validates_sequence(temp_db, sample_user, sample_parts):
    """Test that cassette creation validates assembled sequence."""
    part_ids = [p.id for p in sample_parts]
    
    # Empty sequence
    with pytest.raises(ValueError, match="Assembled sequence cannot be empty"):
        Cassette.create(
            name='Test Cassette',
            owner_id=sample_user.id,
            part_ids=part_ids,
            assembled_sequence=''
        )
    
    # Invalid DNA characters
    with pytest.raises(ValueError, match="Assembled sequence must contain only A, T, C, G characters"):
        Cassette.create(
            name='Test Cassette',
            owner_id=sample_user.id,
            part_ids=part_ids,
            assembled_sequence='ATCGXYZ'
        )


def test_get_cassette_by_id(temp_db, sample_user, sample_parts):
    """Test retrieving a cassette by ID."""
    part_ids = [p.id for p in sample_parts]
    created_cassette = Cassette.create(
        name='Test Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    # Retrieve cassette by ID
    retrieved_cassette = Cassette.get_by_id(created_cassette.id)
    
    assert retrieved_cassette is not None
    assert retrieved_cassette.id == created_cassette.id
    assert retrieved_cassette.name == created_cassette.name
    assert retrieved_cassette.owner_id == created_cassette.owner_id
    assert retrieved_cassette.part_ids == created_cassette.part_ids
    assert retrieved_cassette.assembled_sequence == created_cassette.assembled_sequence


def test_get_cassette_by_id_not_found(temp_db):
    """Test that get_by_id returns None for non-existent cassette."""
    cassette = Cassette.get_by_id('non-existent-id')
    assert cassette is None


def test_get_cassettes_by_owner(temp_db, sample_user, sample_parts):
    """Test retrieving all cassettes owned by a specific user."""
    part_ids = [p.id for p in sample_parts[:2]]
    
    # Create multiple cassettes for the user
    cassette1 = Cassette.create(
        name='Cassette 1',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    cassette2 = Cassette.create(
        name='Cassette 2',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='GCTAGCTAGCTA'
    )
    
    # Retrieve cassettes by owner
    owner_cassettes = Cassette.get_by_owner(sample_user.id)
    
    assert len(owner_cassettes) == 2
    cassette_ids = [c.id for c in owner_cassettes]
    assert cassette1.id in cassette_ids
    assert cassette2.id in cassette_ids


def test_get_cassettes_by_owner_empty(temp_db, sample_user):
    """Test that get_by_owner returns empty list when user has no cassettes."""
    cassettes = Cassette.get_by_owner(sample_user.id)
    assert cassettes == []


def test_get_cassettes_by_owner_isolation(temp_db, sample_parts):
    """Test that get_by_owner only returns cassettes for the specified user."""
    # Create two users
    user1 = User.create(username='user1', password='password1')
    user2 = User.create(username='user2', password='password2')
    
    part_ids = [p.id for p in sample_parts[:2]]
    
    # Create cassettes for each user
    cassette1 = Cassette.create(
        name='User 1 Cassette',
        owner_id=user1.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    cassette2 = Cassette.create(
        name='User 2 Cassette',
        owner_id=user2.id,
        part_ids=part_ids,
        assembled_sequence='GCTAGCTAGCTA'
    )
    
    # User 1 should only see their cassette
    user1_cassettes = Cassette.get_by_owner(user1.id)
    assert len(user1_cassettes) == 1
    assert user1_cassettes[0].id == cassette1.id
    
    # User 2 should only see their cassette
    user2_cassettes = Cassette.get_by_owner(user2.id)
    assert len(user2_cassettes) == 1
    assert user2_cassettes[0].id == cassette2.id


def test_delete_cassette(temp_db, sample_user, sample_parts):
    """Test deleting a cassette."""
    part_ids = [p.id for p in sample_parts]
    cassette = Cassette.create(
        name='Test Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    cassette_id = cassette.id
    
    # Delete cassette
    cassette.delete()
    
    # Cassette should no longer exist
    assert Cassette.get_by_id(cassette_id) is None


def test_get_all_cassettes(temp_db, sample_user, sample_parts):
    """Test retrieving all cassettes."""
    part_ids = [p.id for p in sample_parts[:2]]
    
    # Create multiple cassettes
    cassette1 = Cassette.create(
        name='Cassette 1',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    cassette2 = Cassette.create(
        name='Cassette 2',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='GCTAGCTAGCTA'
    )
    
    # Get all cassettes
    all_cassettes = Cassette.get_all()
    
    assert len(all_cassettes) == 2
    cassette_ids = [c.id for c in all_cassettes]
    assert cassette1.id in cassette_ids
    assert cassette2.id in cassette_ids


def test_get_all_cassettes_empty(temp_db):
    """Test get_all returns empty list when no cassettes exist."""
    cassettes = Cassette.get_all()
    assert cassettes == []


def test_cassette_to_dict(temp_db, sample_user, sample_parts):
    """Test converting cassette to dictionary."""
    part_ids = [p.id for p in sample_parts]
    cassette = Cassette.create(
        name='Test Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    cassette_dict = cassette.to_dict()
    
    assert 'id' in cassette_dict
    assert 'name' in cassette_dict
    assert 'owner_id' in cassette_dict
    assert 'part_ids' in cassette_dict
    assert 'assembled_sequence' in cassette_dict
    assert 'created_at' in cassette_dict
    assert 'length' in cassette_dict
    assert 'part_count' in cassette_dict
    
    assert cassette_dict['id'] == cassette.id
    assert cassette_dict['name'] == cassette.name
    assert cassette_dict['owner_id'] == cassette.owner_id
    assert cassette_dict['part_ids'] == part_ids
    assert cassette_dict['length'] == len(cassette.assembled_sequence)
    assert cassette_dict['part_count'] == len(part_ids)


def test_cassette_repr(temp_db, sample_user, sample_parts):
    """Test cassette string representation."""
    part_ids = [p.id for p in sample_parts]
    cassette = Cassette.create(
        name='Test Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    repr_str = repr(cassette)
    
    assert 'Cassette' in repr_str
    assert cassette.id in repr_str
    assert 'Test Cassette' in repr_str
    assert sample_user.id in repr_str


def test_cassette_equality(temp_db, sample_user, sample_parts):
    """Test cassette equality based on ID."""
    part_ids = [p.id for p in sample_parts[:2]]
    
    cassette1 = Cassette.create(
        name='Cassette 1',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    cassette2 = Cassette.create(
        name='Cassette 2',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='GCTAGCTAGCTA'
    )
    
    # Same cassette retrieved twice should be equal
    cassette1_copy = Cassette.get_by_id(cassette1.id)
    assert cassette1 == cassette1_copy
    
    # Different cassettes should not be equal
    assert cassette1 != cassette2
    
    # Cassette should not equal non-Cassette object
    assert cassette1 != "not a cassette"
    assert cassette1 != None


def test_cassette_created_at_timestamp(temp_db, sample_user, sample_parts):
    """Test that created_at timestamp is set automatically."""
    part_ids = [p.id for p in sample_parts]
    cassette = Cassette.create(
        name='Test Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    assert cassette.created_at is not None
    # Timestamp should be in ISO format (contains date and time)
    assert '-' in cassette.created_at  # Date separator
    assert ':' in cassette.created_at  # Time separator


def test_multiple_cassettes_different_ids(temp_db, sample_user, sample_parts):
    """Test that each cassette gets a unique ID."""
    part_ids = [p.id for p in sample_parts[:2]]
    
    cassette1 = Cassette.create(
        name='Cassette 1',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    cassette2 = Cassette.create(
        name='Cassette 2',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='GCTAGCTAGCTA'
    )
    
    cassette3 = Cassette.create(
        name='Cassette 3',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='TTAATTAATTAA'
    )
    
    # All IDs should be unique
    ids = [cassette1.id, cassette2.id, cassette3.id]
    assert len(ids) == len(set(ids))  # No duplicates


def test_part_ids_stored_as_json(temp_db, sample_user, sample_parts):
    """Test that part_ids list is properly stored and retrieved as JSON."""
    part_ids = [p.id for p in sample_parts]
    cassette = Cassette.create(
        name='Test Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    # Retrieve cassette and verify part_ids is a list
    retrieved_cassette = Cassette.get_by_id(cassette.id)
    assert isinstance(retrieved_cassette.part_ids, list)
    assert retrieved_cassette.part_ids == part_ids


def test_update_cassette_name(temp_db, sample_user, sample_parts):
    """Test updating a cassette's name."""
    part_ids = [p.id for p in sample_parts]
    cassette = Cassette.create(
        name='Old Name',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    # Update name
    cassette.update_name('New Name')
    
    assert cassette.name == 'New Name'
    
    # Verify in database
    retrieved_cassette = Cassette.get_by_id(cassette.id)
    assert retrieved_cassette.name == 'New Name'


def test_update_cassette_name_validates_empty(temp_db, sample_user, sample_parts):
    """Test that update_name validates name is not empty."""
    part_ids = [p.id for p in sample_parts]
    cassette = Cassette.create(
        name='Test Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    with pytest.raises(ValueError, match="Cassette name cannot be empty"):
        cassette.update_name('')
    
    with pytest.raises(ValueError, match="Cassette name cannot be empty"):
        cassette.update_name('   ')


def test_cassette_with_two_parts(temp_db, sample_user, sample_parts):
    """Test creating a cassette with exactly 2 parts (minimum)."""
    part_ids = [sample_parts[0].id, sample_parts[1].id]
    
    cassette = Cassette.create(
        name='Two Part Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    assert len(cassette.part_ids) == 2
    assert cassette.part_ids == part_ids


def test_cassette_with_many_parts(temp_db, sample_user):
    """Test creating a cassette with many parts."""
    # Create 5 parts
    parts = []
    for i in range(5):
        part = Part.create(
            name=f'Part {i}',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor='testuser'
        )
        parts.append(part)
    
    part_ids = [p.id for p in parts]
    
    cassette = Cassette.create(
        name='Multi Part Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG'
    )
    
    assert len(cassette.part_ids) == 5
    assert cassette.part_ids == part_ids


def test_cassette_preserves_part_order(temp_db, sample_user, sample_parts):
    """Test that cassette preserves the order of parts."""
    part_ids = [sample_parts[2].id, sample_parts[0].id, sample_parts[1].id]
    
    cassette = Cassette.create(
        name='Ordered Cassette',
        owner_id=sample_user.id,
        part_ids=part_ids,
        assembled_sequence='ATCGATCGATCG'
    )
    
    # Verify order is preserved
    assert cassette.part_ids == part_ids
    assert cassette.part_ids[0] == sample_parts[2].id
    assert cassette.part_ids[1] == sample_parts[0].id
    assert cassette.part_ids[2] == sample_parts[1].id
    
    # Verify order is preserved after retrieval
    retrieved_cassette = Cassette.get_by_id(cassette.id)
    assert retrieved_cassette.part_ids == part_ids
