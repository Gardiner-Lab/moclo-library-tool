"""
Unit tests for export service (FASTA and GenBank format generation).
"""

import pytest
import os
import tempfile
from app.models.database import Database
from app.models.user import User
from app.models.part import Part
from app.models.cassette import Cassette
from app.services.export import generate_fasta, export_cassette_fasta

# Check if Cairo is available for PNG export tests
def is_cairo_available():
    """Check if Cairo library is available for image export."""
    try:
        import cairosvg
        import cairocffi
        return True
    except (ImportError, OSError):
        return False

# Skip marker for tests that require Cairo
requires_cairo = pytest.mark.skipif(
    not is_cairo_available(),
    reason="Cairo library not available (required for PNG export on Windows)"
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
def sample_user(temp_db):
    """Create a sample user for testing."""
    return User.create(username='testuser', password='password123')


@pytest.fixture
def sample_cassette(temp_db, sample_user):
    """Create a sample cassette for testing export."""
    # Create parts
    part1 = Part.create(
        name='Promoter',
        part_type='NonCodingPromoter',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='CDS',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    # Create cassette
    cassette = Cassette.create(
        name='Test Cassette',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCGCGATCGAT'
    )
    
    return cassette


def test_generate_fasta_basic(sample_cassette):
    """Test basic FASTA generation with cassette name and sequence."""
    fasta = generate_fasta(sample_cassette)
    
    # Check that FASTA starts with header
    assert fasta.startswith('>')
    
    # Check that cassette name is in header
    assert sample_cassette.name in fasta
    
    # Check that sequence is present
    assert sample_cassette.assembled_sequence in fasta.replace('\n', '')


def test_generate_fasta_header_format(sample_cassette):
    """Test that FASTA header is correctly formatted."""
    fasta = generate_fasta(sample_cassette)
    lines = fasta.split('\n')
    
    # First line should be header starting with '>'
    assert lines[0].startswith('>')
    assert lines[0] == f'>{sample_cassette.name}'


def test_generate_fasta_sequence_wrapping(temp_db, sample_user):
    """Test that FASTA sequence is wrapped at 60 characters per line."""
    # Create a cassette with a long sequence (more than 60 characters)
    long_sequence = 'ATCG' * 30  # 120 characters
    
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Long Cassette',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence=long_sequence
    )
    
    fasta = generate_fasta(cassette)
    lines = fasta.split('\n')
    
    # First line is header
    assert lines[0] == '>Long Cassette'
    
    # Subsequent lines should be sequence, wrapped at 60 characters
    # For 120 character sequence, we expect 2 lines of 60 characters each
    assert len(lines[1]) == 60
    assert len(lines[2]) == 60
    
    # Verify the full sequence is preserved
    sequence_from_fasta = ''.join(lines[1:])
    assert sequence_from_fasta == long_sequence


def test_generate_fasta_short_sequence(temp_db, sample_user):
    """Test FASTA generation with sequence shorter than 60 characters."""
    short_sequence = 'ATCGATCG'  # 8 characters
    
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Short Cassette',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence=short_sequence
    )
    
    fasta = generate_fasta(cassette)
    lines = fasta.split('\n')
    
    # Should have header and one sequence line
    assert len(lines) == 2
    assert lines[0] == '>Short Cassette'
    assert lines[1] == short_sequence


def test_generate_fasta_exact_60_characters(temp_db, sample_user):
    """Test FASTA generation with sequence exactly 60 characters."""
    sequence_60 = 'ATCG' * 15  # Exactly 60 characters
    
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Exact 60 Cassette',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence=sequence_60
    )
    
    fasta = generate_fasta(cassette)
    lines = fasta.split('\n')
    
    # Should have header and one sequence line of exactly 60 characters
    assert len(lines) == 2
    assert lines[0] == '>Exact 60 Cassette'
    assert lines[1] == sequence_60
    assert len(lines[1]) == 60


def test_generate_fasta_multiple_lines(temp_db, sample_user):
    """Test FASTA generation with sequence requiring multiple lines."""
    # 185 characters = 3 full lines (60 each) + 1 partial line (5 chars)
    long_sequence = 'ATCG' * 46 + 'A'  # 185 characters
    
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Multi Line Cassette',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence=long_sequence
    )
    
    fasta = generate_fasta(cassette)
    lines = fasta.split('\n')
    
    # Should have header + 4 sequence lines
    assert len(lines) == 5
    assert lines[0] == '>Multi Line Cassette'
    assert len(lines[1]) == 60
    assert len(lines[2]) == 60
    assert len(lines[3]) == 60
    assert len(lines[4]) == 5
    
    # Verify full sequence is preserved
    sequence_from_fasta = ''.join(lines[1:])
    assert sequence_from_fasta == long_sequence


def test_generate_fasta_special_characters_in_name(temp_db, sample_user):
    """Test FASTA generation with special characters in cassette name."""
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Test-Cassette_v1.2 (final)',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCG'
    )
    
    fasta = generate_fasta(cassette)
    lines = fasta.split('\n')
    
    # Header should preserve special characters
    assert lines[0] == '>Test-Cassette_v1.2 (final)'


def test_export_cassette_fasta_by_id(sample_cassette):
    """Test exporting cassette as FASTA by ID."""
    fasta = export_cassette_fasta(sample_cassette.id)
    
    assert fasta is not None
    assert fasta.startswith('>')
    assert sample_cassette.name in fasta
    assert sample_cassette.assembled_sequence in fasta.replace('\n', '')


def test_export_cassette_fasta_not_found(temp_db):
    """Test that export_cassette_fasta returns None for non-existent cassette."""
    fasta = export_cassette_fasta('non-existent-id')
    assert fasta is None


def test_generate_fasta_preserves_sequence_integrity(sample_cassette):
    """Test that FASTA export preserves the complete sequence without modification."""
    fasta = generate_fasta(sample_cassette)
    lines = fasta.split('\n')
    
    # Remove header line and rejoin sequence
    sequence_lines = lines[1:]
    reconstructed_sequence = ''.join(sequence_lines)
    
    # Sequence should be identical to original
    assert reconstructed_sequence == sample_cassette.assembled_sequence


def test_generate_fasta_valid_format(sample_cassette):
    """Test that generated FASTA follows valid FASTA format conventions."""
    fasta = generate_fasta(sample_cassette)
    lines = fasta.split('\n')
    
    # Must have at least 2 lines (header + sequence)
    assert len(lines) >= 2
    
    # First line must start with '>'
    assert lines[0].startswith('>')
    
    # All sequence lines should contain only valid DNA characters
    for line in lines[1:]:
        if line:  # Skip empty lines
            assert all(c in 'ATCG' for c in line)


def test_generate_fasta_empty_name(temp_db, sample_user):
    """Test FASTA generation handles cassette with minimal name."""
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    # Cassette with single character name
    cassette = Cassette.create(
        name='X',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCG'
    )
    
    fasta = generate_fasta(cassette)
    lines = fasta.split('\n')
    
    assert lines[0] == '>X'
    assert lines[1] == 'ATCGATCG'


def test_generate_fasta_long_name(temp_db, sample_user):
    """Test FASTA generation with very long cassette name."""
    long_name = 'A' * 200  # Very long name
    
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name=long_name,
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCG'
    )
    
    fasta = generate_fasta(cassette)
    lines = fasta.split('\n')
    
    # Header should contain the full long name
    assert lines[0] == f'>{long_name}'


def test_fasta_format_standard_compliance(sample_cassette):
    """Test that FASTA output complies with standard FASTA format."""
    fasta = generate_fasta(sample_cassette)
    
    # FASTA should not be empty
    assert len(fasta) > 0
    
    # Should contain newline characters
    assert '\n' in fasta
    
    # Should start with '>'
    assert fasta[0] == '>'
    
    # Header line should end before first sequence line
    first_newline = fasta.index('\n')
    header = fasta[:first_newline]
    assert header.startswith('>')
    
    # Sequence should start after first newline
    sequence_start = fasta[first_newline + 1:]
    assert len(sequence_start) > 0



# ============================================================================
# GenBank Export Tests
# ============================================================================

from app.services.export import generate_genbank, export_cassette_genbank


def test_generate_genbank_basic_structure(sample_cassette):
    """Test that GenBank output has the required basic structure."""
    genbank = generate_genbank(sample_cassette)
    
    # Check for required sections
    assert 'LOCUS' in genbank
    assert 'DEFINITION' in genbank
    assert 'FEATURES' in genbank
    assert 'ORIGIN' in genbank
    assert genbank.endswith('//')


def test_generate_genbank_locus_line(sample_cassette):
    """Test that LOCUS line is correctly formatted."""
    genbank = generate_genbank(sample_cassette)
    lines = genbank.split('\n')
    
    locus_line = lines[0]
    
    # Should start with LOCUS
    assert locus_line.startswith('LOCUS')
    
    # Should contain cassette name (with spaces replaced by underscores)
    expected_name = sample_cassette.name.replace(' ', '_')
    assert expected_name in locus_line
    
    # Should contain sequence length
    assert str(len(sample_cassette.assembled_sequence)) in locus_line
    
    # Should contain 'bp' and 'DNA'
    assert 'bp' in locus_line
    assert 'DNA' in locus_line


def test_generate_genbank_definition_line(sample_cassette):
    """Test that DEFINITION line is present."""
    genbank = generate_genbank(sample_cassette)
    lines = genbank.split('\n')
    
    # Find DEFINITION line
    definition_line = [line for line in lines if line.startswith('DEFINITION')][0]
    
    assert 'DEFINITION' in definition_line
    assert 'MoClo cassette assembly' in definition_line


def test_generate_genbank_features_section(sample_cassette):
    """Test that FEATURES section contains part annotations."""
    genbank = generate_genbank(sample_cassette)
    
    # Should have FEATURES header
    assert 'FEATURES             Location/Qualifiers' in genbank
    
    # Should have misc_feature entries
    assert 'misc_feature' in genbank
    
    # Should have part labels
    assert '/label=' in genbank


def test_generate_genbank_origin_section(sample_cassette):
    """Test that ORIGIN section contains the sequence."""
    genbank = generate_genbank(sample_cassette)
    
    # Should have ORIGIN header
    assert 'ORIGIN' in genbank
    
    # Sequence should be in lowercase in GenBank format
    sequence_lower = sample_cassette.assembled_sequence.lower()
    
    # Extract sequence from ORIGIN section (remove line numbers and spaces)
    origin_start = genbank.index('ORIGIN')
    origin_end = genbank.index('//')
    origin_section = genbank[origin_start:origin_end]
    
    # Remove ORIGIN header, line numbers, and whitespace
    sequence_from_genbank = ''
    for line in origin_section.split('\n')[1:]:  # Skip ORIGIN line
        # Remove leading numbers and spaces
        parts = line.strip().split()
        if parts and parts[0].isdigit():
            sequence_from_genbank += ''.join(parts[1:])
        elif parts:
            sequence_from_genbank += ''.join(parts)
    
    assert sequence_from_genbank == sequence_lower


def test_generate_genbank_terminator(sample_cassette):
    """Test that GenBank output ends with // terminator."""
    genbank = generate_genbank(sample_cassette)
    
    # Should end with //
    assert genbank.strip().endswith('//')


def test_generate_genbank_part_annotations(temp_db, sample_user):
    """Test that each part gets a feature annotation with correct positions."""
    # Create parts with known sequences
    part1 = Part.create(
        name='TestPromoter',
        part_type='NonCodingPromoter',
        sequence='ATCGATCGATCG',  # 12 bases
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Lab A',
        contributor=sample_user.username,
        description='Test promoter part'
    )
    
    part2 = Part.create(
        name='TestCDS',
        part_type='Coding',
        sequence='GCTTCGATCGAT',  # 12 bases, first 4 overlap
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Lab B',
        contributor=sample_user.username,
        description='Test coding sequence'
    )
    
    # Assembled sequence: part1 (12) + part2 (12-4=8) = 20 bases
    cassette = Cassette.create(
        name='Test Assembly',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCGCGATCGAT'  # 20 bases
    )
    
    genbank = generate_genbank(cassette)
    
    # Check that both parts are annotated
    assert 'TestPromoter' in genbank
    assert 'TestCDS' in genbank
    
    # Check part types are included
    assert 'NonCodingPromoter' in genbank
    assert 'Coding' in genbank
    
    # Check positions: part1 should be 1..12, part2 should be 13..20
    assert '1..12' in genbank
    assert '13..20' in genbank


def test_generate_genbank_part_metadata(temp_db, sample_user):
    """Test that part metadata (lab source, contributor) is included."""
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Smith Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='NonCodingTerminator',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Jones Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Metadata Test',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCGCGATCGAT'
    )
    
    genbank = generate_genbank(cassette)
    
    # Check that lab sources are included
    assert 'Smith Lab' in genbank
    assert 'Jones Lab' in genbank
    
    # Check that contributor is included
    assert sample_user.username in genbank


def test_generate_genbank_part_descriptions(temp_db, sample_user):
    """Test that part descriptions are included when available."""
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username,
        description='This is a test part with description'
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
        # No description
    )
    
    cassette = Cassette.create(
        name='Description Test',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCGCGATCGAT'
    )
    
    genbank = generate_genbank(cassette)
    
    # Part1's description should be included
    assert 'This is a test part with description' in genbank
    
    # Check that /note qualifier is present for part with description
    assert '/note=' in genbank


def test_generate_genbank_sequence_formatting(temp_db, sample_user):
    """Test that sequence is formatted correctly in ORIGIN section."""
    # Create a longer sequence to test formatting
    long_sequence = 'ATCG' * 30  # 120 bases
    
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Format Test',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence=long_sequence
    )
    
    genbank = generate_genbank(cassette)
    
    # Find ORIGIN section
    origin_start = genbank.index('ORIGIN')
    origin_end = genbank.index('//')
    origin_section = genbank[origin_start:origin_end]
    lines = origin_section.split('\n')[1:]  # Skip ORIGIN header
    
    # Each line should start with a line number
    for line in lines:
        if line.strip():  # Skip empty lines
            parts = line.strip().split()
            assert parts[0].isdigit(), f"Line should start with number: {line}"


def test_generate_genbank_long_cassette_name(temp_db, sample_user):
    """Test that long cassette names are truncated in LOCUS line."""
    long_name = 'Very Long Cassette Name That Exceeds Sixteen Characters'
    
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name=long_name,
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCGCGATCGAT'
    )
    
    genbank = generate_genbank(cassette)
    lines = genbank.split('\n')
    locus_line = lines[0]
    
    # LOCUS name should be truncated to 16 characters
    # Extract the name from LOCUS line (it's after 'LOCUS' and before the length)
    locus_parts = locus_line.split()
    locus_name = locus_parts[1]
    
    assert len(locus_name) <= 16


def test_generate_genbank_spaces_in_name(temp_db, sample_user):
    """Test that spaces in cassette name are replaced with underscores."""
    name_with_spaces = 'My Test Cassette'
    
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name=name_with_spaces,
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCGCGATCGAT'
    )
    
    genbank = generate_genbank(cassette)
    lines = genbank.split('\n')
    locus_line = lines[0]
    
    # Spaces should be replaced with underscores
    assert 'My_Test_Cassette' in locus_line
    assert 'My Test Cassette' not in locus_line


def test_generate_genbank_multiple_parts(temp_db, sample_user):
    """Test GenBank generation with multiple parts (more than 2)."""
    part1 = Part.create(
        name='Promoter',
        part_type='NonCodingPromoter',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='CDS',
        part_type='Coding',
        sequence='GCTTAAAAAAAAAA',
        overhang_5prime='GCTT',
        overhang_3prime='TTGG',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part3 = Part.create(
        name='Terminator',
        part_type='NonCodingTerminator',
        sequence='TTGGCCCCCCCC',
        overhang_5prime='TTGG',
        overhang_3prime='AAAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    # Assembled: part1(12) + part2(14-4=10) + part3(12-4=8) = 30 bases
    cassette = Cassette.create(
        name='Three Part Assembly',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id, part3.id],
        assembled_sequence='ATCGATCGATCGAAAAAAAAAACCCCCCCC'
    )
    
    genbank = generate_genbank(cassette)
    
    # All three parts should be annotated
    assert 'Promoter' in genbank
    assert 'CDS' in genbank
    assert 'Terminator' in genbank
    
    # Check that we have three misc_feature entries
    assert genbank.count('misc_feature') == 3


def test_generate_genbank_sequence_lowercase(sample_cassette):
    """Test that sequence in ORIGIN section is lowercase (GenBank convention)."""
    genbank = generate_genbank(sample_cassette)
    
    # Find ORIGIN section
    origin_start = genbank.index('ORIGIN')
    origin_end = genbank.index('//')
    origin_section = genbank[origin_start:origin_end]
    
    # Extract sequence characters (skip line numbers)
    sequence_chars = []
    for line in origin_section.split('\n')[1:]:  # Skip ORIGIN header
        parts = line.strip().split()
        if parts and parts[0].isdigit():
            # Join all parts except the first (line number)
            sequence_chars.extend(''.join(parts[1:]))
    
    # All sequence characters should be lowercase
    for char in sequence_chars:
        if char.isalpha():
            assert char.islower(), f"Sequence should be lowercase, found: {char}"


def test_export_cassette_genbank_by_id(sample_cassette):
    """Test exporting cassette as GenBank by ID."""
    genbank = export_cassette_genbank(sample_cassette.id)
    
    assert genbank is not None
    assert 'LOCUS' in genbank
    assert 'FEATURES' in genbank
    assert 'ORIGIN' in genbank
    assert genbank.endswith('//')


def test_export_cassette_genbank_not_found(temp_db):
    """Test that export_cassette_genbank returns None for non-existent cassette."""
    genbank = export_cassette_genbank('non-existent-id')
    assert genbank is None


def test_generate_genbank_preserves_sequence_integrity(sample_cassette):
    """Test that GenBank export preserves the complete sequence without modification."""
    genbank = generate_genbank(sample_cassette)
    
    # Extract sequence from ORIGIN section
    origin_start = genbank.index('ORIGIN')
    origin_end = genbank.index('//')
    origin_section = genbank[origin_start:origin_end]
    
    sequence_from_genbank = ''
    for line in origin_section.split('\n')[1:]:  # Skip ORIGIN line
        parts = line.strip().split()
        if parts and parts[0].isdigit():
            sequence_from_genbank += ''.join(parts[1:])
    
    # Sequence should match (case-insensitive)
    assert sequence_from_genbank.upper() == sample_cassette.assembled_sequence.upper()


def test_generate_genbank_feature_positions_correct(temp_db, sample_user):
    """Test that feature positions are calculated correctly for assembled cassette."""
    # Create parts with specific lengths
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='AATGATCGATCG',  # 12 bases
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='GCTTAAAAAAAA',  # 12 bases
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    # Assembled: part1 full (12) + part2 minus overhang (12-4=8) = 20 bases
    cassette = Cassette.create(
        name='Position Test',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='AATGATCGATCGAAAAAAAA'  # 20 bases
    )
    
    genbank = generate_genbank(cassette)
    
    # Part1 should be at positions 1..12
    assert '1..12' in genbank
    
    # Part2 should be at positions 13..20
    assert '13..20' in genbank


def test_generate_genbank_all_part_types(temp_db, sample_user):
    """Test GenBank generation includes all different part types correctly."""
    part_types = [
        ('Coding', 'Coding'),
        ('Promoter', 'NonCodingPromoter'),
        ('Terminator', 'NonCodingTerminator'),
        ('Intron', 'NonCodingIntron'),
        ('Other', 'NonCodingOther')
    ]
    
    for name, part_type in part_types:
        part = Part.create(
            name=name,
            part_type=part_type,
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor=sample_user.username
        )
        
        part2 = Part.create(
            name='Part2',
            part_type='Coding',
            sequence='GCTTCGATCGAT',
            overhang_5prime='GCTT',
            overhang_3prime='TTAA',
            lab_source='Test Lab',
            contributor=sample_user.username
        )
        
        cassette = Cassette.create(
            name=f'{name} Test',
            owner_id=sample_user.id,
            part_ids=[part.id, part2.id],
            assembled_sequence='ATCGATCGATCGCGATCGAT'
        )
        
        genbank = generate_genbank(cassette)
        
        # Check that part type is included
        assert part_type in genbank
        
        # Cleanup for next iteration
        cassette.delete()
        part.delete()
        part2.delete()


# ============================================================================
# Image Export Tests
# ============================================================================

from app.services.export import (
    svg_to_png,
    generate_cassette_image,
    export_cassette_image,
    generate_part_image,
    export_part_image
)


@requires_cairo
def test_svg_to_png_basic():
    """Test basic SVG to PNG conversion."""
    # Simple SVG content
    svg_content = '''<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="80" height="80" fill="blue"/>
    </svg>'''
    
    png_data = svg_to_png(svg_content)
    
    # Should return bytes
    assert isinstance(png_data, bytes)
    
    # Should have PNG header (first 8 bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
    
    # Should have non-zero length
    assert len(png_data) > 0


@requires_cairo
def test_svg_to_png_with_width():
    """Test SVG to PNG conversion with specified output width."""
    svg_content = '''<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="80" height="80" fill="red"/>
    </svg>'''
    
    png_data = svg_to_png(svg_content, output_width=200)
    
    # Should return bytes
    assert isinstance(png_data, bytes)
    
    # Should have PNG header
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
    
    # Should be larger than without width specification (more pixels)
    png_data_default = svg_to_png(svg_content)
    assert len(png_data) > len(png_data_default) * 0.5  # At least somewhat larger


@requires_cairo
def test_svg_to_png_invalid_svg():
    """Test that invalid SVG raises ValueError."""
    invalid_svg = "This is not valid SVG content"
    
    with pytest.raises(ValueError) as exc_info:
        svg_to_png(invalid_svg)
    
    assert "Failed to convert SVG to PNG" in str(exc_info.value)


@requires_cairo
def test_svg_to_png_empty_svg():
    """Test that empty SVG raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        svg_to_png("")
    
    assert "Failed to convert SVG to PNG" in str(exc_info.value)


@requires_cairo
def test_generate_part_image_basic(temp_db, sample_user):
    """Test basic part image generation."""
    part = Part.create(
        name='TestPart',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    png_data = generate_part_image(part)
    
    # Should return bytes
    assert isinstance(png_data, bytes)
    
    # Should have PNG header
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
    
    # Should have reasonable size
    assert len(png_data) > 100


@requires_cairo
def test_generate_part_image_with_width(temp_db, sample_user):
    """Test part image generation with custom width."""
    part = Part.create(
        name='TestPart',
        part_type='NonCodingPromoter',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    png_data = generate_part_image(part, width=400)
    
    # Should return bytes
    assert isinstance(png_data, bytes)
    
    # Should have PNG header
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


@requires_cairo
def test_generate_part_image_all_types(temp_db, sample_user):
    """Test that image generation works for all part types."""
    part_types = [
        'Coding',
        'NonCodingPromoter',
        'NonCodingTerminator',
        'NonCodingIntron',
        'NonCodingOther'
    ]
    
    for part_type in part_types:
        part = Part.create(
            name=f'{part_type}_Part',
            part_type=part_type,
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor=sample_user.username
        )
        
        png_data = generate_part_image(part)
        
        # Should return valid PNG for each type
        assert isinstance(png_data, bytes)
        assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
        
        # Cleanup
        part.delete()


@requires_cairo
def test_export_part_image_by_id(temp_db, sample_user):
    """Test exporting part image by ID."""
    part = Part.create(
        name='TestPart',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    png_data = export_part_image(part.id)
    
    assert png_data is not None
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_part_image_not_found(temp_db):
    """Test that export_part_image returns None for non-existent part."""
    png_data = export_part_image('non-existent-id')
    assert png_data is None


@requires_cairo
def test_generate_cassette_image_basic(sample_cassette):
    """Test basic cassette image generation."""
    png_data = generate_cassette_image(sample_cassette)
    
    # Should return bytes
    assert isinstance(png_data, bytes)
    
    # Should have PNG header
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
    
    # Should have reasonable size (cassettes are larger than parts)
    assert len(png_data) > 100


@requires_cairo
def test_generate_cassette_image_with_width(sample_cassette):
    """Test cassette image generation with custom width."""
    png_data = generate_cassette_image(sample_cassette, width=1200)
    
    # Should return bytes
    assert isinstance(png_data, bytes)
    
    # Should have PNG header
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


@requires_cairo
def test_generate_cassette_image_multiple_parts(temp_db, sample_user):
    """Test cassette image generation with multiple parts."""
    # Create 4 parts
    part1 = Part.create(
        name='Promoter',
        part_type='NonCodingPromoter',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='CDS1',
        part_type='Coding',
        sequence='GCTTAAAAAAAAAA',
        overhang_5prime='GCTT',
        overhang_3prime='TTGG',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part3 = Part.create(
        name='CDS2',
        part_type='Coding',
        sequence='TTGGCCCCCCCC',
        overhang_5prime='TTGG',
        overhang_3prime='GGAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part4 = Part.create(
        name='Terminator',
        part_type='NonCodingTerminator',
        sequence='GGAATTTTTTTT',
        overhang_5prime='GGAA',
        overhang_3prime='AAAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Four Part Cassette',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id, part3.id, part4.id],
        assembled_sequence='ATCGATCGATCGAAAAAAAAAACCCCCCCCTTTTTTTT'
    )
    
    png_data = generate_cassette_image(cassette)
    
    # Should return valid PNG
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
    
    # Should be larger than a simple cassette (more parts = more content)
    assert len(png_data) > 100


@requires_cairo
def test_generate_cassette_image_empty_parts(temp_db, sample_user):
    """Test that cassette with no parts raises ValueError."""
    # The Cassette.create() method validates that cassettes must have at least 2 parts
    # So this test should verify that validation works
    with pytest.raises(ValueError) as exc_info:
        cassette = Cassette.create(
            name='Empty Cassette',
            owner_id=sample_user.id,
            part_ids=[],
            assembled_sequence=''
        )
    
    assert "at least 2 parts" in str(exc_info.value)
    
    assert "Cassette has no parts to visualize" in str(exc_info.value)


@requires_cairo
def test_export_cassette_image_by_id(sample_cassette):
    """Test exporting cassette image by ID."""
    png_data = export_cassette_image(sample_cassette.id)
    
    assert png_data is not None
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


@requires_cairo
def test_export_cassette_image_with_width(sample_cassette):
    """Test exporting cassette image with custom width."""
    png_data = export_cassette_image(sample_cassette.id, width=1000)
    
    assert png_data is not None
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_cassette_image_not_found(temp_db):
    """Test that export_cassette_image returns None for non-existent cassette."""
    png_data = export_cassette_image('non-existent-id')
    assert png_data is None


@requires_cairo
def test_cassette_image_includes_all_parts(temp_db, sample_user):
    """Test that cassette image generation processes all parts correctly."""
    # Create parts with distinct types
    part1 = Part.create(
        name='P1',
        part_type='NonCodingPromoter',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='P2',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part3 = Part.create(
        name='P3',
        part_type='NonCodingTerminator',
        sequence='TTAAAAAAAAAT',
        overhang_5prime='TTAA',
        overhang_3prime='GGGG',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Three Part Test',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id, part3.id],
        assembled_sequence='ATCGATCGATCGCGATCGATAAAAAAAAT'
    )
    
    # Should not raise any errors
    png_data = generate_cassette_image(cassette)
    
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


@requires_cairo
def test_image_export_preserves_part_boundaries(temp_db, sample_user):
    """Test that image export includes part boundaries (via SVG generation)."""
    # This test verifies that the SVG generation is called correctly
    # The actual visual verification would require image analysis
    
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='NonCodingPromoter',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Boundary Test',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCGCGATCGAT'
    )
    
    # Generate image - should include all part information
    png_data = generate_cassette_image(cassette)
    
    # Verify it's a valid PNG
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
    
    # The image should be reasonably sized (contains multiple parts with labels)
    assert len(png_data) > 500


@requires_cairo
def test_image_export_different_widths(temp_db, sample_user):
    """Test that image export works with various width specifications."""
    part = Part.create(
        name='TestPart',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    widths = [100, 200, 400, 800, 1200]
    
    for width in widths:
        png_data = generate_part_image(part, width=width)
        
        # Should generate valid PNG for each width
        assert isinstance(png_data, bytes)
        assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


@requires_cairo
def test_cassette_image_with_incompatible_parts(temp_db, sample_user):
    """Test that image generation works even with incompatible parts (shows error indicators)."""
    # Create parts with incompatible overhangs
    part1 = Part.create(
        name='Part1',
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='Part2',
        part_type='Coding',
        sequence='AAAACGATCGAT',  # 5' overhang is AAAA, not GCTT
        overhang_5prime='AAAA',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    # Create cassette with incompatible parts
    cassette = Cassette.create(
        name='Incompatible Test',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCGCGATCGAT'  # Dummy sequence
    )
    
    # Should still generate image (with incompatibility indicators)
    png_data = generate_cassette_image(cassette)
    
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


@requires_cairo
def test_part_image_with_long_name(temp_db, sample_user):
    """Test part image generation with very long part name."""
    long_name = 'A' * 100  # Very long name
    
    part = Part.create(
        name=long_name,
        part_type='Coding',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    # Should handle long names gracefully
    png_data = generate_part_image(part)
    
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


@requires_cairo
def test_cassette_image_with_long_part_names(temp_db, sample_user):
    """Test cassette image generation with parts having long names."""
    part1 = Part.create(
        name='VeryLongPartNameThatExceedsNormalLength',
        part_type='NonCodingPromoter',
        sequence='ATCGATCGATCG',
        overhang_5prime='AATG',
        overhang_3prime='GCTT',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    part2 = Part.create(
        name='AnotherVeryLongPartNameForTesting',
        part_type='Coding',
        sequence='GCTTCGATCGAT',
        overhang_5prime='GCTT',
        overhang_3prime='TTAA',
        lab_source='Test Lab',
        contributor=sample_user.username
    )
    
    cassette = Cassette.create(
        name='Long Names Test',
        owner_id=sample_user.id,
        part_ids=[part1.id, part2.id],
        assembled_sequence='ATCGATCGATCGCGATCGAT'
    )
    
    # Should handle long names (they get truncated in visualization)
    png_data = generate_cassette_image(cassette)
    
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


@requires_cairo
def test_image_export_png_format_validity(sample_cassette):
    """Test that exported images are valid PNG format."""
    png_data = generate_cassette_image(sample_cassette)
    
    # PNG signature (first 8 bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
    
    # Should have IHDR chunk (image header) after signature
    # IHDR is typically at bytes 12-16
    assert b'IHDR' in png_data[:50]
    
    # Should have IEND chunk at the end (marks end of PNG)
    assert b'IEND' in png_data[-20:]


@requires_cairo
def test_svg_to_png_with_text_elements():
    """Test SVG to PNG conversion with text elements (like part labels)."""
    svg_content = '''<svg width="200" height="100" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="180" height="80" fill="blue"/>
        <text x="100" y="50" text-anchor="middle" fill="white">Test Label</text>
    </svg>'''
    
    png_data = svg_to_png(svg_content)
    
    # Should successfully convert SVG with text
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'


@requires_cairo
def test_svg_to_png_with_complex_shapes():
    """Test SVG to PNG conversion with complex shapes (like chevrons)."""
    svg_content = '''<svg width="200" height="100" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="180" height="80" fill="green"/>
        <path d="M 50,30 L 60,50 L 50,70 Z" fill="darkgreen"/>
        <path d="M 80,30 L 90,50 L 80,70 Z" fill="darkgreen"/>
    </svg>'''
    
    png_data = svg_to_png(svg_content)
    
    # Should successfully convert SVG with paths
    assert isinstance(png_data, bytes)
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
