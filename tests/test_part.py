"""
Unit tests for Part model with CRUD operations, search, and filter methods.
"""

import pytest
import os
import tempfile
from app.models.database import Database
from app.models.user import User
from app.models.part import Part


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
def test_user(temp_db):
    """Create a test user for part creation."""
    return User.create(username='testuser', password='password123')


def test_part_creation(temp_db, test_user):
    """Test creating a new part with all required fields."""
    part = Part.create(
        name='Test Promoter',
        part_type='NonCodingPromoter',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=test_user.username,
        description='A test promoter part'
    )
    
    assert part.id is not None
    assert part.name == 'Test Promoter'
    assert part.part_type == 'NonCodingPromoter'
    assert part.sequence == 'ATCGATCGATCG'
    assert part.overhang_5prime == 'AATG'
    assert part.overhang_3prime == 'GCTT'
    assert part.lab_source == 'Test Lab'
    assert part.contributor == test_user.username
    assert part.description == 'A test promoter part'
    assert part.upload_date is not None


def test_part_creation_without_description(temp_db, test_user):
    """Test creating a part without optional description."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    assert part.id is not None
    assert part.description is None


def test_part_creation_validates_name(temp_db, test_user):
    """Test that empty part name raises error."""
    with pytest.raises(ValueError, match="Part name cannot be empty"):
        Part.create(
            name='',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor=test_user.username
        )
    
    with pytest.raises(ValueError, match="Part name cannot be empty"):
        Part.create(
            name='   ',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor=test_user.username
        )


def test_part_creation_validates_part_type(temp_db, test_user):
    """Test that invalid part type raises error."""
    with pytest.raises(ValueError, match="Invalid part type"):
        Part.create(
            name='Test Part',
            part_type='InvalidType',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor=test_user.username
        )


def test_part_creation_validates_sequence(temp_db, test_user):
    """Test that invalid DNA sequence raises error."""
    # Invalid characters
    with pytest.raises(ValueError, match="Sequence must contain only A, T, C, G"):
        Part.create(
            name='Test Part',
            part_type='Coding',
            sequence='ATCGXYZ',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor=test_user.username
        )
    
    # Too short
    with pytest.raises(ValueError, match="Sequence must be at least 8 bases long"):
        Part.create(
            name='Test Part',
            part_type='Coding',
            sequence='ATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor=test_user.username
        )


def test_part_creation_validates_overhangs(temp_db, test_user):
    """Test that invalid overhangs raise errors."""
    # 5' overhang too short
    with pytest.raises(ValueError, match="5' overhang must be exactly 4 DNA bases"):
        Part.create(
            name='Test Part',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AAT',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor=test_user.username
        )
    
    # 5' overhang too long
    with pytest.raises(ValueError, match="5' overhang must be exactly 4 DNA bases"):
        Part.create(
            name='Test Part',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATGG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor=test_user.username
        )
    
    # 3' overhang invalid characters
    with pytest.raises(ValueError, match="3' overhang must be exactly 4 DNA bases"):
        Part.create(
            name='Test Part',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCXX',
            lab_source='Test Lab',
            contributor=test_user.username
        )


def test_part_creation_validates_lab_source(temp_db, test_user):
    """Test that empty lab source raises error."""
    with pytest.raises(ValueError, match="Lab source cannot be empty"):
        Part.create(
            name='Test Part',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='',
            contributor=test_user.username
        )


def test_get_part_by_id(temp_db, test_user):
    """Test retrieving a part by ID."""
    created_part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    retrieved_part = Part.get_by_id(created_part.id)
    
    assert retrieved_part is not None
    assert retrieved_part.id == created_part.id
    assert retrieved_part.name == created_part.name
    assert retrieved_part.part_type == created_part.part_type
    assert retrieved_part.sequence == created_part.sequence


def test_get_part_by_id_not_found(temp_db):
    """Test that get_by_id returns None for non-existent part."""
    part = Part.get_by_id('non-existent-id')
    assert part is None


def test_get_all_parts(temp_db, test_user):
    """Test retrieving all parts."""
    part1 = Part.create(
        name='Part 1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Part 2',
        part_type='NonCodingPromoter',
        sequence='GCTAGCTAGCTA',
        overhang_5prime='TTAA',
        overhang_3prime='CCGG',
        lab_source='Lab 2',
        contributor=test_user.username
    )
    
    all_parts = Part.get_all()
    
    assert len(all_parts) == 2
    part_names = [p.name for p in all_parts]
    assert 'Part 1' in part_names
    assert 'Part 2' in part_names


def test_get_all_parts_empty(temp_db):
    """Test get_all returns empty list when no parts exist."""
    parts = Part.get_all()
    assert parts == []


def test_filter_by_type(temp_db, test_user):
    """Test filtering parts by type."""
    # Create parts of different types
    Part.create(
        name='Coding Part 1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    Part.create(
        name='Coding Part 2',
        part_type='Coding',
        sequence='GCTAGCTAGCTA',
        overhang_5prime='TTAA',
        overhang_3prime='CCGG',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    Part.create(
        name='Promoter Part',
        part_type='NonCodingPromoter',
        sequence='AAAATTTTCCCC',
        overhang_5prime='GGCC',
        overhang_3prime='AATT',
        lab_source='Lab 2',
        contributor=test_user.username
    )
    
    # Filter by Coding type
    coding_parts = Part.filter_by_type('Coding')
    assert len(coding_parts) == 2
    assert all(p.part_type == 'Coding' for p in coding_parts)
    
    # Filter by NonCodingPromoter type
    promoter_parts = Part.filter_by_type('NonCodingPromoter')
    assert len(promoter_parts) == 1
    assert promoter_parts[0].name == 'Promoter Part'


def test_filter_by_type_invalid_type(temp_db):
    """Test that filtering by invalid type raises error."""
    with pytest.raises(ValueError, match="Invalid part type"):
        Part.filter_by_type('InvalidType')


def test_filter_by_type_no_matches(temp_db, test_user):
    """Test filtering by type with no matches returns empty list."""
    Part.create(
        name='Coding Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    terminator_parts = Part.filter_by_type('NonCodingTerminator')
    assert terminator_parts == []


def test_search_by_name(temp_db, test_user):
    """Test searching parts by name."""
    Part.create(
        name='GFP Coding Sequence',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    Part.create(
        name='RFP Coding Sequence',
        part_type='Coding',
        sequence='GCTAGCTAGCTA',
        overhang_5prime='TTAA',
        overhang_3prime='CCGG',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    Part.create(
        name='T7 Promoter',
        part_type='NonCodingPromoter',
        sequence='AAAATTTTCCCC',
        overhang_5prime='GGCC',
        overhang_3prime='AATT',
        lab_source='Lab 2',
        contributor=test_user.username
    )
    
    # Search for "GFP"
    results = Part.search('GFP')
    assert len(results) == 1
    assert results[0].name == 'GFP Coding Sequence'
    
    # Search for "Coding" (partial match)
    results = Part.search('Coding')
    assert len(results) == 2
    
    # Search for "Promoter"
    results = Part.search('Promoter')
    assert len(results) == 1
    assert results[0].name == 'T7 Promoter'


def test_search_case_insensitive(temp_db, test_user):
    """Test that search is case-insensitive."""
    Part.create(
        name='GFP Coding Sequence',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    # Search with different cases
    results_lower = Part.search('gfp')
    results_upper = Part.search('GFP')
    results_mixed = Part.search('Gfp')
    
    assert len(results_lower) == 1
    assert len(results_upper) == 1
    assert len(results_mixed) == 1


def test_search_no_matches(temp_db, test_user):
    """Test search with no matches returns empty list."""
    Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    results = Part.search('NonExistent')
    assert results == []


def test_find_compatible_before(temp_db, test_user):
    """Test finding parts that can be placed before a target part."""
    # Create target part with 5' overhang AATG
    target = Part.create(
        name='Target Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    # Create compatible part (3' overhang matches target's 5' overhang)
    compatible = Part.create(
        name='Compatible Part',
        part_type='NonCodingPromoter',
        sequence='GCTAGCTAGCTA',
        overhang_5prime='TTAA',
        overhang_3prime='AATG',  # Matches target's 5' overhang
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    # Create incompatible part
    incompatible = Part.create(
        name='Incompatible Part',
        part_type='NonCodingTerminator',
        sequence='AAAATTTTCCCC',
        overhang_5prime='GGCC',
        overhang_3prime='CCGG',  # Does not match
        lab_source='Lab 2',
        contributor=test_user.username
    )
    
    # Find compatible parts before target
    before_parts = Part.find_compatible_before(target)
    
    assert len(before_parts) == 1
    assert before_parts[0].id == compatible.id
    assert before_parts[0].name == 'Compatible Part'


def test_find_compatible_after(temp_db, test_user):
    """Test finding parts that can be placed after a target part."""
    # Create target part with 3' overhang GCTT
    target = Part.create(
        name='Target Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    # Create compatible part (5' overhang matches target's 3' overhang)
    compatible = Part.create(
        name='Compatible Part',
        part_type='NonCodingTerminator',
        sequence='GCTAGCTAGCTA',
        overhang_5prime='GCTT',  # Matches target's 3' overhang
        overhang_3prime='AATT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    # Create incompatible part
    incompatible = Part.create(
        name='Incompatible Part',
        part_type='NonCodingPromoter',
        sequence='AAAATTTTCCCC',
        overhang_5prime='GGCC',  # Does not match
        overhang_3prime='CCGG',
        lab_source='Lab 2',
        contributor=test_user.username
    )
    
    # Find compatible parts after target
    after_parts = Part.find_compatible_after(target)
    
    assert len(after_parts) == 1
    assert after_parts[0].id == compatible.id
    assert after_parts[0].name == 'Compatible Part'


def test_find_compatible_excludes_self(temp_db, test_user):
    """Test that compatibility search excludes the part itself."""
    # Create a part that could be compatible with itself
    part = Part.create(
        name='Self Compatible Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='AATG',  # Same as 5' overhang
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    # Should not find itself
    before_parts = Part.find_compatible_before(part)
    after_parts = Part.find_compatible_after(part)
    
    assert len(before_parts) == 0
    assert len(after_parts) == 0


def test_update_part_name(temp_db, test_user):
    """Test updating a part's name."""
    part = Part.create(
        name='Old Name',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    part.update(name='New Name')
    
    assert part.name == 'New Name'
    
    # Verify in database
    retrieved = Part.get_by_id(part.id)
    assert retrieved.name == 'New Name'


def test_update_part_type(temp_db, test_user):
    """Test updating a part's type."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    part.update(part_type='NonCodingPromoter')
    
    assert part.part_type == 'NonCodingPromoter'


def test_update_part_type_invalid(temp_db, test_user):
    """Test that updating to invalid part type raises error."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    with pytest.raises(ValueError, match="Invalid part type"):
        part.update(part_type='InvalidType')


def test_update_part_sequence(temp_db, test_user):
    """Test updating a part's sequence."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    part.update(sequence='GCTAGCTAGCTA')
    
    assert part.sequence == 'GCTAGCTAGCTA'


def test_update_part_sequence_invalid(temp_db, test_user):
    """Test that updating to invalid sequence raises error."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    with pytest.raises(ValueError, match="Sequence must contain only A, T, C, G"):
        part.update(sequence='ATCGXYZ')


def test_update_overhangs(temp_db, test_user):
    """Test updating part overhangs."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    part.update(overhang_5prime='TTAA', overhang_3prime='CCGG')
    
    assert part.overhang_5prime == 'TTAA'
    assert part.overhang_3prime == 'CCGG'


def test_update_overhang_invalid(temp_db, test_user):
    """Test that updating to invalid overhang raises error."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    with pytest.raises(ValueError, match="5' overhang must be exactly 4 DNA bases"):
        part.update(overhang_5prime='AAT')


def test_update_multiple_fields(temp_db, test_user):
    """Test updating multiple fields simultaneously."""
    part = Part.create(
        name='Old Name',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username,
        description='Old description'
    )
    
    part.update(
        name='New Name',
        part_type='NonCodingPromoter',
        description='New description'
    )
    
    assert part.name == 'New Name'
    assert part.part_type == 'NonCodingPromoter'
    assert part.description == 'New description'


def test_delete_part(temp_db, test_user):
    """Test deleting a part."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    part_id = part.id
    part.delete()
    
    # Part should no longer exist
    assert Part.get_by_id(part_id) is None


def test_part_to_dict(temp_db, test_user):
    """Test converting part to dictionary."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username,
        description='Test description'
    )
    
    part_dict = part.to_dict()
    
    assert part_dict['id'] == part.id
    assert part_dict['name'] == 'Test Part'
    assert part_dict['part_type'] == 'Coding'
    assert part_dict['sequence'] == 'ATCGATCGATCG'
    assert part_dict['overhang_5prime'] == 'AATG'
    assert part_dict['overhang_3prime'] == 'GCTT'
    assert part_dict['lab_source'] == 'Lab 1'
    assert part_dict['contributor'] == test_user.username
    assert part_dict['description'] == 'Test description'
    assert part_dict['length'] == 12  # Length of sequence


def test_part_repr(temp_db, test_user):
    """Test part string representation."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    repr_str = repr(part)
    
    assert 'Part' in repr_str
    assert part.id in repr_str
    assert 'Test Part' in repr_str
    assert 'Coding' in repr_str


def test_part_equality(temp_db, test_user):
    """Test part equality based on ID."""
    part1 = Part.create(
        name='Part 1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Part 2',
        part_type='NonCodingPromoter',
        sequence='GCTAGCTAGCTA',
        overhang_5prime='TTAA',
        overhang_3prime='CCGG',
        lab_source='Lab 2',
        contributor=test_user.username
    )
    
    # Same part retrieved twice should be equal
    part1_copy = Part.get_by_id(part1.id)
    assert part1 == part1_copy
    
    # Different parts should not be equal
    assert part1 != part2
    
    # Part should not equal non-Part object
    assert part1 != "not a part"
    assert part1 != None


def test_valid_part_types(temp_db, test_user):
    """Test that all valid part types can be created."""
    valid_types = [
        'Coding',
        'NonCodingPromoter',
        'NonCodingTerminator',
        'NonCodingIntron',
        'NonCodingOther'
    ]
    
    for part_type in valid_types:
        part = Part.create(
            name=f'Test {part_type}',
            part_type=part_type,
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Lab 1',
            contributor=test_user.username
        )
        assert part.part_type == part_type


def test_part_upload_date_timestamp(temp_db, test_user):
    """Test that upload_date timestamp is set automatically."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    assert part.upload_date is not None
    # Timestamp should be in ISO format
    assert '-' in part.upload_date  # Date separator
    assert ':' in part.upload_date  # Time separator


def test_multiple_parts_different_ids(temp_db, test_user):
    """Test that each part gets a unique ID."""
    part1 = Part.create(
        name='Part 1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab 1',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Part 2',
        part_type='NonCodingPromoter',
        sequence='GCTAGCTAGCTA',
        overhang_5prime='TTAA',
        overhang_3prime='CCGG',
        lab_source='Lab 2',
        contributor=test_user.username
    )
    
    part3 = Part.create(
        name='Part 3',
        part_type='NonCodingTerminator',
        sequence='AAAATTTTCCCC',
        overhang_5prime='GGCC',
        overhang_3prime='AATT',
        lab_source='Lab 3',
        contributor=test_user.username
    )
    
    # All IDs should be unique
    ids = [part1.id, part2.id, part3.id]
    assert len(ids) == len(set(ids))  # No duplicates
