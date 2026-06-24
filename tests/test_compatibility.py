"""
Unit tests for compatibility checker service.

Tests the functions that check part compatibility based on overhang sequences,
find compatible parts, and validate assembly orders.
"""

import pytest
import os
import tempfile
from app.models.database import Database
from app.models.user import User
from app.models.part import Part
from app.services.compatibility import (
    are_compatible,
    find_compatible_parts,
    validate_assembly,
    get_compatibility_info
)


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


@pytest.fixture
def sample_parts(temp_db, test_user):
    """Create a set of sample parts for testing compatibility."""
    # Create a chain of compatible parts:
    # part1 (AAAA -> TTTT) -> part2 (TTTT -> GGGG) -> part3 (GGGG -> CCCC)
    
    part1 = Part.create(
        name='Part 1',
        part_type='NonCodingPromoter',
        sequence='AAAATTTTGGGG',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username,
        description='First part in chain'
    )
    
    part2 = Part.create(
        name='Part 2',
        part_type='Coding',
        sequence='TTTTGGGGCCCC',
        overhang_5prime='TTTT',
        overhang_3prime='GGGG',
        lab_source='Test Lab',
        contributor=test_user.username,
        description='Second part in chain'
    )
    
    part3 = Part.create(
        name='Part 3',
        part_type='NonCodingTerminator',
        sequence='GGGGCCCCAAAA',
        overhang_5prime='GGGG',
        overhang_3prime='CCCC',
        lab_source='Test Lab',
        contributor=test_user.username,
        description='Third part in chain'
    )
    
    # Create an incompatible part
    part_incompatible = Part.create(
        name='Incompatible Part',
        part_type='NonCodingOther',
        sequence='ATCGATCGATCG',
        overhang_5prime='ATCG',
        overhang_3prime='CGAT',
        lab_source='Test Lab',
        contributor=test_user.username,
        description='Part with different overhangs'
    )
    
    return {
        'part1': part1,
        'part2': part2,
        'part3': part3,
        'incompatible': part_incompatible
    }


# Tests for are_compatible function

def test_are_compatible_matching_overhangs(sample_parts):
    """Test that parts with matching overhangs are compatible."""
    part1 = sample_parts['part1']
    part2 = sample_parts['part2']
    
    # part1's 3' overhang (TTTT) matches part2's 5' overhang (TTTT)
    assert are_compatible(part1, part2) is True


def test_are_compatible_non_matching_overhangs(sample_parts):
    """Test that parts with non-matching overhangs are not compatible."""
    part1 = sample_parts['part1']
    part3 = sample_parts['part3']
    
    # part1's 3' overhang (TTTT) does not match part3's 5' overhang (GGGG)
    assert are_compatible(part1, part3) is False


def test_are_compatible_reverse_order(sample_parts):
    """Test that compatibility is directional (order matters)."""
    part1 = sample_parts['part1']
    part2 = sample_parts['part2']
    
    # part1 -> part2 is compatible
    assert are_compatible(part1, part2) is True
    
    # part2 -> part1 is not compatible
    assert are_compatible(part2, part1) is False


def test_are_compatible_with_incompatible_part(sample_parts):
    """Test compatibility check with completely incompatible part."""
    part1 = sample_parts['part1']
    incompatible = sample_parts['incompatible']
    
    assert are_compatible(part1, incompatible) is False
    assert are_compatible(incompatible, part1) is False


def test_are_compatible_same_part(temp_db, test_user):
    """Test compatibility of a part with itself (edge case)."""
    # Create a part where 3' overhang equals 5' overhang
    part = Part.create(
        name='Self Compatible',
        part_type='Coding',
        sequence='AAAATTTTGGGG',
        overhang_5prime='AAAA',
        overhang_3prime='AAAA',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    # A part is compatible with itself if overhangs match
    assert are_compatible(part, part) is True


# Tests for find_compatible_parts function

def test_find_compatible_parts_before_and_after(sample_parts):
    """Test finding parts that can be placed before and after a target part."""
    part2 = sample_parts['part2']
    all_parts = [sample_parts['part1'], sample_parts['part2'], 
                 sample_parts['part3'], sample_parts['incompatible']]
    
    result = find_compatible_parts(part2, all_parts)
    
    # part1 can be placed before part2 (part1's 3' = TTTT matches part2's 5' = TTTT)
    assert len(result['before']) == 1
    assert result['before'][0].id == sample_parts['part1'].id
    
    # part3 can be placed after part2 (part2's 3' = GGGG matches part3's 5' = GGGG)
    assert len(result['after']) == 1
    assert result['after'][0].id == sample_parts['part3'].id


def test_find_compatible_parts_excludes_self(sample_parts):
    """Test that find_compatible_parts excludes the target part itself."""
    part1 = sample_parts['part1']
    all_parts = [sample_parts['part1'], sample_parts['part2'], 
                 sample_parts['part3'], sample_parts['incompatible']]
    
    result = find_compatible_parts(part1, all_parts)
    
    # part1 should not be in the results
    before_ids = [p.id for p in result['before']]
    after_ids = [p.id for p in result['after']]
    
    assert part1.id not in before_ids
    assert part1.id not in after_ids


def test_find_compatible_parts_no_matches(sample_parts):
    """Test finding compatible parts when there are no matches."""
    incompatible = sample_parts['incompatible']
    all_parts = [sample_parts['part1'], sample_parts['part2'], 
                 sample_parts['part3'], sample_parts['incompatible']]
    
    result = find_compatible_parts(incompatible, all_parts)
    
    # No parts should be compatible with the incompatible part
    assert len(result['before']) == 0
    assert len(result['after']) == 0


def test_find_compatible_parts_multiple_matches(temp_db, test_user):
    """Test finding compatible parts when multiple parts match."""
    # Create a target part
    target = Part.create(
        name='Target',
        part_type='Coding',
        sequence='TTTTGGGGCCCC',
        overhang_5prime='TTTT',
        overhang_3prime='GGGG',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    # Create multiple parts that can be placed before (3' = TTTT)
    before1 = Part.create(
        name='Before 1',
        part_type='NonCodingPromoter',
        sequence='AAAATTTTCCCC',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    before2 = Part.create(
        name='Before 2',
        part_type='NonCodingPromoter',
        sequence='CCCCTTTTAAAA',
        overhang_5prime='CCCC',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    # Create multiple parts that can be placed after (5' = GGGG)
    after1 = Part.create(
        name='After 1',
        part_type='NonCodingTerminator',
        sequence='GGGGCCCCTTTT',
        overhang_5prime='GGGG',
        overhang_3prime='CCCC',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    after2 = Part.create(
        name='After 2',
        part_type='NonCodingTerminator',
        sequence='GGGGAAAATTTT',
        overhang_5prime='GGGG',
        overhang_3prime='AAAA',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    all_parts = [target, before1, before2, after1, after2]
    result = find_compatible_parts(target, all_parts)
    
    # Should find 2 parts before and 2 parts after
    assert len(result['before']) == 2
    assert len(result['after']) == 2
    
    before_names = {p.name for p in result['before']}
    after_names = {p.name for p in result['after']}
    
    assert before_names == {'Before 1', 'Before 2'}
    assert after_names == {'After 1', 'After 2'}


def test_find_compatible_parts_empty_list(temp_db, test_user):
    """Test finding compatible parts with an empty parts list."""
    part = Part.create(
        name='Test Part',
        part_type='Coding',
        sequence='AAAATTTTGGGG',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    result = find_compatible_parts(part, [])
    
    assert len(result['before']) == 0
    assert len(result['after']) == 0


# Tests for validate_assembly function

def test_validate_assembly_valid_chain(sample_parts):
    """Test validating a valid assembly chain."""
    parts = [sample_parts['part1'], sample_parts['part2'], sample_parts['part3']]
    
    result = validate_assembly(parts)
    
    assert result['valid'] is True
    assert result['error'] == ''
    assert result['incompatible_pair'] is None


def test_validate_assembly_two_parts_valid(sample_parts):
    """Test validating a valid assembly with minimum 2 parts."""
    parts = [sample_parts['part1'], sample_parts['part2']]
    
    result = validate_assembly(parts)
    
    assert result['valid'] is True
    assert result['error'] == ''
    assert result['incompatible_pair'] is None


def test_validate_assembly_insufficient_parts(sample_parts):
    """Test that assembly with less than 2 parts is invalid."""
    # Single part
    result = validate_assembly([sample_parts['part1']])
    
    assert result['valid'] is False
    assert 'at least 2 parts' in result['error']
    assert result['incompatible_pair'] is None
    
    # Empty list
    result = validate_assembly([])
    
    assert result['valid'] is False
    assert 'at least 2 parts' in result['error']
    assert result['incompatible_pair'] is None


def test_validate_assembly_incompatible_parts(sample_parts):
    """Test validating an assembly with incompatible parts."""
    # part1 and part3 are not compatible (part1's 3' = TTTT, part3's 5' = GGGG)
    parts = [sample_parts['part1'], sample_parts['part3']]
    
    result = validate_assembly(parts)
    
    assert result['valid'] is False
    assert 'incompatible overhangs' in result['error']
    assert result['incompatible_pair'] == (0, 1)
    assert 'TTTT' in result['error']  # part1's 3' overhang
    assert 'GGGG' in result['error']  # part3's 5' overhang


def test_validate_assembly_incompatible_in_middle(sample_parts):
    """Test validating an assembly with incompatibility in the middle."""
    # part1 -> part2 is valid, but part2 -> incompatible is not
    parts = [sample_parts['part1'], sample_parts['part2'], sample_parts['incompatible']]
    
    result = validate_assembly(parts)
    
    assert result['valid'] is False
    assert 'incompatible overhangs' in result['error']
    assert result['incompatible_pair'] == (1, 2)  # part2 and incompatible


def test_validate_assembly_error_message_includes_part_names(sample_parts):
    """Test that validation error messages include part names."""
    parts = [sample_parts['part1'], sample_parts['part3']]
    
    result = validate_assembly(parts)
    
    assert result['valid'] is False
    assert 'Part 1' in result['error']
    assert 'Part 3' in result['error']


def test_validate_assembly_error_message_includes_overhangs(sample_parts):
    """Test that validation error messages include overhang sequences."""
    parts = [sample_parts['part1'], sample_parts['part3']]
    
    result = validate_assembly(parts)
    
    assert result['valid'] is False
    assert sample_parts['part1'].overhang_3prime in result['error']
    assert sample_parts['part3'].overhang_5prime in result['error']


def test_validate_assembly_long_valid_chain(temp_db, test_user):
    """Test validating a longer chain of compatible parts."""
    # Create a chain of 5 parts
    parts = []
    overhangs = ['AAAA', 'TTTT', 'GGGG', 'CCCC', 'ATCG', 'CGAT']
    
    for i in range(5):
        part = Part.create(
            name=f'Part {i+1}',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime=overhangs[i],
            overhang_3prime=overhangs[i+1],
            lab_source='Test Lab',
            contributor=test_user.username
        )
        parts.append(part)
    
    result = validate_assembly(parts)
    
    assert result['valid'] is True
    assert result['error'] == ''
    assert result['incompatible_pair'] is None


def test_validate_assembly_identifies_first_incompatibility(temp_db, test_user):
    """Test that validation identifies the first incompatible pair."""
    # Create parts where multiple pairs are incompatible
    part1 = Part.create(
        name='Part 1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Part 2',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='GGGG',  # Doesn't match part1's 3'
        overhang_3prime='CCCC',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part3 = Part.create(
        name='Part 3',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='ATCG',  # Doesn't match part2's 3'
        overhang_3prime='CGAT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    result = validate_assembly([part1, part2, part3])
    
    assert result['valid'] is False
    # Should identify the first incompatible pair (0, 1)
    assert result['incompatible_pair'] == (0, 1)


# Tests for get_compatibility_info function

def test_get_compatibility_info_compatible_parts(sample_parts):
    """Test getting compatibility info for compatible parts."""
    part1 = sample_parts['part1']
    part2 = sample_parts['part2']
    
    info = get_compatibility_info(part1, part2)
    
    assert info['compatible'] is True
    assert info['part1_3prime'] == 'TTTT'
    assert info['part2_5prime'] == 'TTTT'
    assert info['match'] is True
    assert 'compatible' in info['message'].lower()
    assert 'Part 1' in info['message']
    assert 'Part 2' in info['message']


def test_get_compatibility_info_incompatible_parts(sample_parts):
    """Test getting compatibility info for incompatible parts."""
    part1 = sample_parts['part1']
    part3 = sample_parts['part3']
    
    info = get_compatibility_info(part1, part3)
    
    assert info['compatible'] is False
    assert info['part1_3prime'] == 'TTTT'
    assert info['part2_5prime'] == 'GGGG'
    assert info['match'] is False
    assert 'incompatible' in info['message'].lower()
    assert 'Part 1' in info['message']
    assert 'Part 3' in info['message']


def test_get_compatibility_info_message_includes_overhangs(sample_parts):
    """Test that compatibility info message includes overhang sequences."""
    part1 = sample_parts['part1']
    part2 = sample_parts['part2']
    
    info = get_compatibility_info(part1, part2)
    
    assert part1.overhang_3prime in info['message']
    assert part2.overhang_5prime in info['message']


def test_get_compatibility_info_structure(sample_parts):
    """Test that compatibility info has the expected structure."""
    part1 = sample_parts['part1']
    part2 = sample_parts['part2']
    
    info = get_compatibility_info(part1, part2)
    
    # Check all expected keys are present
    assert 'compatible' in info
    assert 'part1_3prime' in info
    assert 'part2_5prime' in info
    assert 'match' in info
    assert 'message' in info
    
    # Check types
    assert isinstance(info['compatible'], bool)
    assert isinstance(info['part1_3prime'], str)
    assert isinstance(info['part2_5prime'], str)
    assert isinstance(info['match'], bool)
    assert isinstance(info['message'], str)


# Integration tests

def test_compatibility_workflow_complete_chain(temp_db, test_user):
    """Test a complete workflow: create parts, find compatible, validate assembly."""
    # Create parts
    part1 = Part.create(
        name='Promoter',
        part_type='NonCodingPromoter',
        sequence='AAAATTTTGGGG',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Gene',
        part_type='Coding',
        sequence='TTTTGGGGCCCC',
        overhang_5prime='TTTT',
        overhang_3prime='GGGG',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part3 = Part.create(
        name='Terminator',
        part_type='NonCodingTerminator',
        sequence='GGGGCCCCAAAA',
        overhang_5prime='GGGG',
        overhang_3prime='CCCC',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    # Find compatible parts for part2
    all_parts = [part1, part2, part3]
    compatible = find_compatible_parts(part2, all_parts)
    
    assert len(compatible['before']) == 1
    assert compatible['before'][0].name == 'Promoter'
    assert len(compatible['after']) == 1
    assert compatible['after'][0].name == 'Terminator'
    
    # Validate the assembly
    assembly = [part1, part2, part3]
    validation = validate_assembly(assembly)
    
    assert validation['valid'] is True


def test_compatibility_workflow_invalid_assembly(temp_db, test_user):
    """Test workflow with invalid assembly detection."""
    # Create parts that don't form a valid chain
    part1 = Part.create(
        name='Part A',
        part_type='Coding',
        sequence='AAAATTTTGGGG',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Part B',
        part_type='Coding',
        sequence='GGGGCCCCAAAA',
        overhang_5prime='GGGG',  # Doesn't match part1's 3'
        overhang_3prime='CCCC',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    # Check compatibility
    assert are_compatible(part1, part2) is False
    
    # Validate assembly
    validation = validate_assembly([part1, part2])
    
    assert validation['valid'] is False
    assert validation['incompatible_pair'] == (0, 1)


def test_edge_case_circular_compatibility(temp_db, test_user):
    """Test edge case where parts could form a circular assembly."""
    # Create parts where the last part's 3' matches the first part's 5'
    part1 = Part.create(
        name='Part 1',
        part_type='Coding',
        sequence='AAAATTTTGGGG',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Part 2',
        part_type='Coding',
        sequence='TTTTGGGGAAAA',
        overhang_5prime='TTTT',
        overhang_3prime='GGGG',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part3 = Part.create(
        name='Part 3',
        part_type='Coding',
        sequence='GGGGCCCCAAAA',
        overhang_5prime='GGGG',
        overhang_3prime='AAAA',  # Matches part1's 5'
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    # Linear assembly should be valid
    validation = validate_assembly([part1, part2, part3])
    assert validation['valid'] is True
    
    # The last part is compatible with the first (circular)
    assert are_compatible(part3, part1) is True
