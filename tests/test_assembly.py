"""
Unit tests for assembly service.

Tests the functions that assemble parts into cassettes, validate assemblies,
and generate appropriate error messages for invalid assemblies.
"""

import pytest
import os
import tempfile
from app.models.database import Database
from app.models.user import User
from app.models.part import Part
from app.models.cassette import Cassette
from app.services.assembly import (
    assemble_parts,
    create_cassette,
    validate_parts_for_assembly,
    get_assembly_preview,
    disassemble_cassette,
    verify_cassette_assembly,
    AssemblyError
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
    """Create a test user for part and cassette creation."""
    return User.create(username='testuser', password='password123')


@pytest.fixture
def compatible_parts(temp_db, test_user):
    """Create a set of compatible parts for testing assembly."""
    # Create a chain of 3 compatible parts:
    # part1 (AAAA -> TTTT) -> part2 (TTTT -> GGGG) -> part3 (GGGG -> CCCC)
    
    part1 = Part.create(
        name='Promoter',
        part_type='NonCodingPromoter',
        sequence='AAAATTTTGGGGCCCC',  # 16 bases
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username,
        description='Promoter part'
    )
    
    part2 = Part.create(
        name='Gene',
        part_type='Coding',
        sequence='TTTTGGGGCCCCAAAA',  # 16 bases
        overhang_5prime='TTTT',
        overhang_3prime='GGGG',
        lab_source='Test Lab',
        contributor=test_user.username,
        description='Coding sequence'
    )
    
    part3 = Part.create(
        name='Terminator',
        part_type='NonCodingTerminator',
        sequence='GGGGCCCCAAAATTTT',  # 16 bases
        overhang_5prime='GGGG',
        overhang_3prime='CCCC',
        lab_source='Test Lab',
        contributor=test_user.username,
        description='Terminator part'
    )
    
    return [part1, part2, part3]


@pytest.fixture
def incompatible_parts(temp_db, test_user):
    """Create parts that are not compatible for testing error cases."""
    part1 = Part.create(
        name='Part A',
        part_type='Coding',
        sequence='AAAATTTTGGGGCCCC',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Part B',
        part_type='Coding',
        sequence='GGGGCCCCAAAATTTT',
        overhang_5prime='GGGG',  # Doesn't match part1's 3' (TTTT)
        overhang_3prime='CCCC',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    return [part1, part2]


# Tests for assemble_parts function

def test_assemble_parts_two_parts(compatible_parts):
    """Test assembling two compatible parts."""
    parts = compatible_parts[:2]  # part1 and part2
    
    assembled = assemble_parts(parts)
    
    # Expected: part1 full sequence + part2 sequence minus first 4 bases
    # part1: AAAATTTTGGGGCCCC (16 bases)
    # part2: TTTTGGGGCCCCAAAA (16 bases, skip first 4)
    # Result: AAAATTTTGGGGCCCC + GGGGCCCCAAAA = AAAATTTTGGGGCCCCGGGGCCCCAAAA (28 bases)
    expected = 'AAAATTTTGGGGCCCC' + 'GGGGCCCCAAAA'
    
    assert assembled == expected
    assert len(assembled) == 28


def test_assemble_parts_three_parts(compatible_parts):
    """Test assembling three compatible parts."""
    assembled = assemble_parts(compatible_parts)
    
    # Expected: part1 full + part2 minus 4 + part3 minus 4
    # part1: AAAATTTTGGGGCCCC (16 bases)
    # part2: TTTTGGGGCCCCAAAA (skip 4, add 12)
    # part3: GGGGCCCCAAAATTTT (skip 4, add 12)
    # Result: 16 + 12 + 12 = 40 bases
    expected = 'AAAATTTTGGGGCCCC' + 'GGGGCCCCAAAA' + 'CCCCAAAATTTT'
    
    assert assembled == expected
    assert len(assembled) == 40


def test_assemble_parts_incompatible_raises_error(incompatible_parts):
    """Test that assembling incompatible parts raises AssemblyError."""
    with pytest.raises(AssemblyError) as exc_info:
        assemble_parts(incompatible_parts)
    
    # Error message should mention incompatible overhangs
    assert 'incompatible overhangs' in str(exc_info.value).lower()


def test_assemble_parts_single_part_raises_error(compatible_parts):
    """Test that assembling a single part raises AssemblyError."""
    with pytest.raises(AssemblyError) as exc_info:
        assemble_parts([compatible_parts[0]])
    
    assert 'at least 2 parts' in str(exc_info.value).lower()


def test_assemble_parts_empty_list_raises_error():
    """Test that assembling an empty list raises AssemblyError."""
    with pytest.raises(AssemblyError) as exc_info:
        assemble_parts([])
    
    assert 'at least 2 parts' in str(exc_info.value).lower()


def test_assemble_parts_no_overhang_duplication(temp_db, test_user):
    """Test that overhangs are not duplicated in the assembled sequence."""
    # Create parts with distinctive sequences to verify no duplication
    part1 = Part.create(
        name='Part 1',
        part_type='Coding',
        sequence='AAAATTTTCCCCGGGG',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Part 2',
        part_type='Coding',
        sequence='TTTTGGGGAAAACCCC',
        overhang_5prime='TTTT',
        overhang_3prime='GGGG',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    assembled = assemble_parts([part1, part2])
    
    # The TTTT overhang should appear only once at the junction
    # part1: AAAATTTTCCCCGGGG
    # part2: TTTTGGGGAAAACCCC (skip first TTTT)
    # Result: AAAATTTTCCCCGGGG + GGGGAAAACCCC
    expected = 'AAAATTTTCCCCGGGG' + 'GGGGAAAACCCC'
    
    assert assembled == expected
    # Verify TTTT appears only once at the junction (not duplicated)
    assert assembled.count('TTTT') == 1


def test_assemble_parts_preserves_sequence_order(compatible_parts):
    """Test that parts are assembled in the correct order."""
    assembled = assemble_parts(compatible_parts)
    
    # The assembled sequence should start with part1's sequence
    assert assembled.startswith(compatible_parts[0].sequence)
    
    # And should end with part3's sequence (minus first 4 bases)
    assert assembled.endswith(compatible_parts[2].sequence[4:])


def test_assemble_parts_long_chain(temp_db, test_user):
    """Test assembling a longer chain of parts."""
    # Create 5 compatible parts
    parts = []
    overhangs = ['AAAA', 'TTTT', 'GGGG', 'CCCC', 'ATCG', 'CGAT']
    
    for i in range(5):
        part = Part.create(
            name=f'Part {i+1}',
            part_type='Coding',
            sequence='ATCGATCGATCGATCG',  # 16 bases
            overhang_5prime=overhangs[i],
            overhang_3prime=overhangs[i+1],
            lab_source='Test Lab',
            contributor=test_user.username
        )
        parts.append(part)
    
    assembled = assemble_parts(parts)
    
    # Expected length: 16 + (12 * 4) = 16 + 48 = 64 bases
    assert len(assembled) == 64


# Tests for create_cassette function

def test_create_cassette_valid_parts(compatible_parts, test_user):
    """Test creating a cassette from valid compatible parts."""
    cassette = create_cassette(
        name='Test Cassette',
        owner_id=test_user.id,
        parts=compatible_parts
    )
    
    assert cassette is not None
    assert cassette.name == 'Test Cassette'
    assert cassette.owner_id == test_user.id
    assert len(cassette.part_ids) == 3
    assert cassette.part_ids == [p.id for p in compatible_parts]
    assert len(cassette.assembled_sequence) == 40  # As calculated before


def test_create_cassette_incompatible_parts_raises_error(incompatible_parts, test_user):
    """Test that creating a cassette from incompatible parts raises AssemblyError."""
    with pytest.raises(AssemblyError):
        create_cassette(
            name='Invalid Cassette',
            owner_id=test_user.id,
            parts=incompatible_parts
        )


def test_create_cassette_empty_name_raises_error(compatible_parts, test_user):
    """Test that creating a cassette with empty name raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        create_cassette(
            name='',
            owner_id=test_user.id,
            parts=compatible_parts
        )
    
    assert 'name' in str(exc_info.value).lower()


def test_create_cassette_persists_to_database(compatible_parts, test_user):
    """Test that created cassette is persisted to database."""
    cassette = create_cassette(
        name='Persistent Cassette',
        owner_id=test_user.id,
        parts=compatible_parts
    )
    
    # Retrieve from database
    retrieved = Cassette.get_by_id(cassette.id)
    
    assert retrieved is not None
    assert retrieved.id == cassette.id
    assert retrieved.name == cassette.name
    assert retrieved.owner_id == cassette.owner_id
    assert retrieved.part_ids == cassette.part_ids
    assert retrieved.assembled_sequence == cassette.assembled_sequence


def test_create_cassette_associates_with_owner(compatible_parts, test_user, temp_db):
    """Test that cassette is associated with the correct owner."""
    # Create another user
    user2 = User.create(username='user2', password='password123')
    
    # Create cassette for user1
    cassette1 = create_cassette(
        name='User1 Cassette',
        owner_id=test_user.id,
        parts=compatible_parts
    )
    
    # Create cassette for user2
    cassette2 = create_cassette(
        name='User2 Cassette',
        owner_id=user2.id,
        parts=compatible_parts
    )
    
    # Verify ownership
    user1_cassettes = Cassette.get_by_owner(test_user.id)
    user2_cassettes = Cassette.get_by_owner(user2.id)
    
    assert len(user1_cassettes) == 1
    assert user1_cassettes[0].id == cassette1.id
    
    assert len(user2_cassettes) == 1
    assert user2_cassettes[0].id == cassette2.id


# Tests for validate_parts_for_assembly function

def test_validate_parts_for_assembly_valid(compatible_parts):
    """Test validating a valid assembly."""
    part_ids = [p.id for p in compatible_parts]
    
    result = validate_parts_for_assembly(part_ids)
    
    assert result['valid'] is True
    assert result['error'] == ''
    assert result['parts'] is not None
    assert len(result['parts']) == 3
    assert result['assembled_length'] == 40


def test_validate_parts_for_assembly_insufficient_parts(compatible_parts):
    """Test validation with less than 2 parts."""
    result = validate_parts_for_assembly([compatible_parts[0].id])
    
    assert result['valid'] is False
    assert 'at least 2 parts' in result['error'].lower()
    assert result['parts'] is None


def test_validate_parts_for_assembly_nonexistent_part(compatible_parts):
    """Test validation with a non-existent part ID."""
    part_ids = [compatible_parts[0].id, 'nonexistent-id']
    
    result = validate_parts_for_assembly(part_ids)
    
    assert result['valid'] is False
    assert 'not found' in result['error'].lower()
    assert result['parts'] is None


def test_validate_parts_for_assembly_incompatible(incompatible_parts):
    """Test validation with incompatible parts."""
    part_ids = [p.id for p in incompatible_parts]
    
    result = validate_parts_for_assembly(part_ids)
    
    assert result['valid'] is False
    assert 'incompatible' in result['error'].lower()
    assert result['parts'] is not None  # Parts exist, just incompatible


def test_validate_parts_for_assembly_calculates_length(compatible_parts):
    """Test that validation correctly calculates assembled length."""
    part_ids = [p.id for p in compatible_parts[:2]]
    
    result = validate_parts_for_assembly(part_ids)
    
    assert result['valid'] is True
    # part1: 16 bases, part2: 16 bases - 4 = 12 bases
    # Total: 28 bases
    assert result['assembled_length'] == 28


# Tests for get_assembly_preview function

def test_get_assembly_preview_valid(compatible_parts):
    """Test getting a preview of a valid assembly."""
    preview = get_assembly_preview(compatible_parts)
    
    assert preview['valid'] is True
    assert preview['error'] == ''
    assert len(preview['sequence']) == 40
    assert preview['length'] == 40
    assert preview['part_count'] == 3
    assert len(preview['junctions']) == 2


def test_get_assembly_preview_invalid(incompatible_parts):
    """Test getting a preview of an invalid assembly."""
    preview = get_assembly_preview(incompatible_parts)
    
    assert preview['valid'] is False
    assert preview['error'] != ''
    assert preview['sequence'] == ''
    assert preview['length'] == 0
    assert preview['part_count'] == 2
    assert len(preview['junctions']) == 0


def test_get_assembly_preview_junction_info(compatible_parts):
    """Test that preview includes correct junction information."""
    preview = get_assembly_preview(compatible_parts)
    
    assert len(preview['junctions']) == 2
    
    # First junction: part1 -> part2
    junction1 = preview['junctions'][0]
    assert junction1['part1_name'] == 'Promoter'
    assert junction1['part2_name'] == 'Gene'
    assert junction1['overhang'] == 'TTTT'
    assert junction1['position'] == 0
    
    # Second junction: part2 -> part3
    junction2 = preview['junctions'][1]
    assert junction2['part1_name'] == 'Gene'
    assert junction2['part2_name'] == 'Terminator'
    assert junction2['overhang'] == 'GGGG'
    assert junction2['position'] == 1


def test_get_assembly_preview_includes_part_ids(compatible_parts):
    """Test that preview includes part IDs in junction info."""
    preview = get_assembly_preview(compatible_parts)
    
    junction = preview['junctions'][0]
    assert 'part1_id' in junction
    assert 'part2_id' in junction
    assert junction['part1_id'] == compatible_parts[0].id
    assert junction['part2_id'] == compatible_parts[1].id


# Tests for disassemble_cassette function

def test_disassemble_cassette(compatible_parts, test_user):
    """Test disassembling a cassette into its component parts."""
    # Create a cassette
    cassette = create_cassette(
        name='Test Cassette',
        owner_id=test_user.id,
        parts=compatible_parts
    )
    
    # Disassemble it
    parts = disassemble_cassette(cassette)
    
    assert len(parts) == 3
    assert parts[0].id == compatible_parts[0].id
    assert parts[1].id == compatible_parts[1].id
    assert parts[2].id == compatible_parts[2].id


def test_disassemble_cassette_preserves_order(compatible_parts, test_user):
    """Test that disassembly preserves part order."""
    cassette = create_cassette(
        name='Test Cassette',
        owner_id=test_user.id,
        parts=compatible_parts
    )
    
    parts = disassemble_cassette(cassette)
    
    # Verify order is preserved
    for i, part in enumerate(parts):
        assert part.id == compatible_parts[i].id
        assert part.name == compatible_parts[i].name


def test_disassemble_cassette_missing_part_raises_error(compatible_parts, test_user, temp_db):
    """Test that disassembly fails if a part is missing from database."""
    # Create a cassette
    cassette = create_cassette(
        name='Test Cassette',
        owner_id=test_user.id,
        parts=compatible_parts
    )
    
    # Delete one of the parts
    compatible_parts[1].delete()
    
    # Try to disassemble
    with pytest.raises(ValueError) as exc_info:
        disassemble_cassette(cassette)
    
    assert 'not found' in str(exc_info.value).lower()


# Tests for verify_cassette_assembly function

def test_verify_cassette_assembly_valid(compatible_parts, test_user):
    """Test verifying a valid cassette assembly."""
    cassette = create_cassette(
        name='Test Cassette',
        owner_id=test_user.id,
        parts=compatible_parts
    )
    
    verification = verify_cassette_assembly(cassette)
    
    assert verification['valid'] is True
    assert verification['error'] == ''
    assert verification['match'] is True
    assert verification['expected_sequence'] == verification['actual_sequence']


def test_verify_cassette_assembly_corrupted(compatible_parts, test_user, temp_db):
    """Test verifying a cassette with corrupted sequence."""
    # Create a cassette normally
    cassette = create_cassette(
        name='Test Cassette',
        owner_id=test_user.id,
        parts=compatible_parts
    )
    
    # Manually corrupt the sequence in the database
    from app.models.database import get_database
    db = get_database()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cassettes SET assembled_sequence = ? WHERE id = ?",
            ('CORRUPTED', cassette.id)
        )
    
    # Reload the cassette
    cassette = Cassette.get_by_id(cassette.id)
    
    # Verify should detect the corruption
    verification = verify_cassette_assembly(cassette)
    
    assert verification['valid'] is False
    assert verification['match'] is False
    assert 'mismatch' in verification['error'].lower()


def test_verify_cassette_assembly_includes_sequences(compatible_parts, test_user):
    """Test that verification includes both expected and actual sequences."""
    cassette = create_cassette(
        name='Test Cassette',
        owner_id=test_user.id,
        parts=compatible_parts
    )
    
    verification = verify_cassette_assembly(cassette)
    
    assert 'expected_sequence' in verification
    assert 'actual_sequence' in verification
    assert len(verification['expected_sequence']) > 0
    assert len(verification['actual_sequence']) > 0


# Integration tests

def test_full_assembly_workflow(temp_db, test_user):
    """Test complete workflow: create parts, validate, assemble, verify."""
    # Create parts
    part1 = Part.create(
        name='Promoter',
        part_type='NonCodingPromoter',
        sequence='AAAATTTTGGGGCCCC',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    part2 = Part.create(
        name='Gene',
        part_type='Coding',
        sequence='TTTTGGGGCCCCAAAA',
        overhang_5prime='TTTT',
        overhang_3prime='GGGG',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    # Validate
    validation = validate_parts_for_assembly([part1.id, part2.id])
    assert validation['valid'] is True
    
    # Preview
    preview = get_assembly_preview([part1, part2])
    assert preview['valid'] is True
    assert preview['length'] == 28
    
    # Create cassette
    cassette = create_cassette(
        name='My Construct',
        owner_id=test_user.id,
        parts=[part1, part2]
    )
    assert cassette is not None
    
    # Verify
    verification = verify_cassette_assembly(cassette)
    assert verification['valid'] is True
    
    # Disassemble
    parts = disassemble_cassette(cassette)
    assert len(parts) == 2
    assert parts[0].id == part1.id
    assert parts[1].id == part2.id


def test_assembly_error_messages_are_descriptive(incompatible_parts):
    """Test that assembly errors provide helpful information."""
    try:
        assemble_parts(incompatible_parts)
        assert False, "Should have raised AssemblyError"
    except AssemblyError as e:
        error_msg = str(e)
        # Error should mention part names
        assert 'Part A' in error_msg or 'Part B' in error_msg
        # Error should mention the incompatible overhangs
        assert 'TTTT' in error_msg or 'GGGG' in error_msg
        # Error should indicate incompatibility
        assert 'incompatible' in error_msg.lower()


def test_assembly_with_different_part_types(temp_db, test_user):
    """Test assembling parts of different types."""
    # Create parts of all different types
    promoter = Part.create(
        name='Promoter',
        part_type='NonCodingPromoter',
        sequence='AAAATTTTGGGGCCCC',
        overhang_5prime='AAAA',
        overhang_3prime='TTTT',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    gene = Part.create(
        name='Gene',
        part_type='Coding',
        sequence='TTTTGGGGCCCCAAAA',
        overhang_5prime='TTTT',
        overhang_3prime='GGGG',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    intron = Part.create(
        name='Intron',
        part_type='NonCodingIntron',
        sequence='GGGGCCCCAAAATTTT',
        overhang_5prime='GGGG',
        overhang_3prime='CCCC',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    terminator = Part.create(
        name='Terminator',
        part_type='NonCodingTerminator',
        sequence='CCCCAAAATTTTGGGG',
        overhang_5prime='CCCC',
        overhang_3prime='ATCG',
        lab_source='Test Lab',
        contributor=test_user.username
    )
    
    # Assemble all types
    parts = [promoter, gene, intron, terminator]
    cassette = create_cassette(
        name='Multi-Type Cassette',
        owner_id=test_user.id,
        parts=parts
    )
    
    assert cassette is not None
    assert len(cassette.part_ids) == 4
    
    # Verify assembly
    verification = verify_cassette_assembly(cassette)
    assert verification['valid'] is True
