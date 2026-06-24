"""
Unit tests for the part validation service.

Tests validation functions for DNA sequences, overhangs, duplicate parts,
and required fields according to Requirements 10.2, 10.4, 10.7.
"""

import pytest
import os
import tempfile
from app.services.validation import (
    validate_dna_sequence,
    validate_overhang_format,
    check_duplicate_part,
    validate_required_fields,
    validate_part_type,
    validate_part_for_upload,
    is_valid_dna_sequence,
    is_valid_overhang,
    ValidationError
)
from app.models.part import Part
from app.models.database import Database
import app.models.database as db_module


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    # Reset the global database instance
    db_module._db_instance = None
    
    # Initialize the database
    db = Database(db_path)
    db.initialize_schema()
    
    # Set as global instance
    db_module._db_instance = db
    
    yield db
    
    # Reset the global instance
    db_module._db_instance = None
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestValidateDNASequence:
    """Tests for DNA sequence validation (Requirement 10.2)."""
    
    def test_valid_dna_sequence(self):
        """Test that valid DNA sequences pass validation."""
        # Should not raise any exception
        validate_dna_sequence("ATCGATCG")
        validate_dna_sequence("AAAATTTTCCCCGGGG")
        validate_dna_sequence("atcgatcg")  # lowercase should work
        validate_dna_sequence("AtCgAtCg")  # mixed case should work
    
    def test_empty_sequence(self):
        """Test that empty sequences are rejected."""
        with pytest.raises(ValidationError, match="Sequence cannot be empty"):
            validate_dna_sequence("")
    
    def test_sequence_with_invalid_characters(self):
        """Test that sequences with non-ATCG characters are rejected."""
        with pytest.raises(ValidationError, match="Invalid characters found"):
            validate_dna_sequence("ATCGXYZ")
        
        with pytest.raises(ValidationError, match="Invalid characters found"):
            validate_dna_sequence("ATCG123")
        
        with pytest.raises(ValidationError, match="Invalid characters found"):
            validate_dna_sequence("ATCG-ATCG")
    
    def test_sequence_too_short(self):
        """Test that sequences shorter than 8 bases are rejected."""
        with pytest.raises(ValidationError, match="at least 8 bases long"):
            validate_dna_sequence("ATCG")
        
        with pytest.raises(ValidationError, match="at least 8 bases long"):
            validate_dna_sequence("ATCGATC")  # 7 bases
    
    def test_sequence_minimum_length(self):
        """Test that sequences of exactly 8 bases are accepted."""
        validate_dna_sequence("ATCGATCG")  # Should not raise


class TestValidateOverhangFormat:
    """Tests for overhang format validation (Requirement 10.4)."""
    
    def test_valid_overhang(self):
        """Test that valid 4-base overhangs pass validation."""
        validate_overhang_format("ATCG")
        validate_overhang_format("AAAA")
        validate_overhang_format("atcg")  # lowercase
        validate_overhang_format("AtCg")  # mixed case
    
    def test_empty_overhang(self):
        """Test that empty overhangs are rejected."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_overhang_format("")
    
    def test_overhang_wrong_length(self):
        """Test that overhangs not exactly 4 bases are rejected."""
        with pytest.raises(ValidationError, match="exactly 4 bases long"):
            validate_overhang_format("ATC")  # 3 bases
        
        with pytest.raises(ValidationError, match="exactly 4 bases long"):
            validate_overhang_format("ATCGA")  # 5 bases
        
        with pytest.raises(ValidationError, match="exactly 4 bases long"):
            validate_overhang_format("AT")  # 2 bases
    
    def test_overhang_invalid_characters(self):
        """Test that overhangs with non-ATCG characters are rejected."""
        with pytest.raises(ValidationError, match="Invalid characters found"):
            validate_overhang_format("ATCX")
        
        with pytest.raises(ValidationError, match="Invalid characters found"):
            validate_overhang_format("12CG")
    
    def test_custom_overhang_name(self):
        """Test that custom overhang names appear in error messages."""
        with pytest.raises(ValidationError, match="5' overhang"):
            validate_overhang_format("ATC", "5' overhang")
        
        with pytest.raises(ValidationError, match="3' overhang"):
            validate_overhang_format("ATCGA", "3' overhang")


class TestCheckDuplicatePart:
    """Tests for duplicate part checking (Requirement 10.7)."""
    
    def test_no_duplicate_in_empty_database(self, temp_db):
        """Test that no duplicates are found in an empty database."""
        result = check_duplicate_part("ATCGATCG", "AATG", "GCTT")
        assert result is False
    
    def test_duplicate_detected(self, temp_db):
        """Test that duplicates are correctly detected."""
        # Create a part
        Part.create(
            name="Test Part",
            part_type="Coding",
            sequence="ATCGATCGATCG",
            overhang_5prime="AATG",
            overhang_3prime="GCTT",
            lab_source="Test Lab",
            contributor="testuser"
        )
        
        # Check for duplicate with same sequence and overhangs
        result = check_duplicate_part("ATCGATCGATCG", "AATG", "GCTT")
        assert result is True
    
    def test_no_duplicate_different_sequence(self, temp_db):
        """Test that parts with different sequences are not considered duplicates."""
        # Create a part
        Part.create(
            name="Test Part",
            part_type="Coding",
            sequence="ATCGATCGATCG",
            overhang_5prime="AATG",
            overhang_3prime="GCTT",
            lab_source="Test Lab",
            contributor="testuser"
        )
        
        # Check with different sequence
        result = check_duplicate_part("GGGGAAAACCCC", "AATG", "GCTT")
        assert result is False
    
    def test_no_duplicate_different_overhangs(self, temp_db):
        """Test that parts with different overhangs are not considered duplicates."""
        # Create a part
        Part.create(
            name="Test Part",
            part_type="Coding",
            sequence="ATCGATCGATCG",
            overhang_5prime="AATG",
            overhang_3prime="GCTT",
            lab_source="Test Lab",
            contributor="testuser"
        )
        
        # Check with different 5' overhang
        result = check_duplicate_part("ATCGATCGATCG", "TTTT", "GCTT")
        assert result is False
        
        # Check with different 3' overhang
        result = check_duplicate_part("ATCGATCGATCG", "AATG", "AAAA")
        assert result is False
    
    def test_exclude_id_parameter(self, temp_db):
        """Test that exclude_id parameter works correctly."""
        # Create a part
        part = Part.create(
            name="Test Part",
            part_type="Coding",
            sequence="ATCGATCGATCG",
            overhang_5prime="AATG",
            overhang_3prime="GCTT",
            lab_source="Test Lab",
            contributor="testuser"
        )
        
        # Check for duplicate excluding the part itself
        result = check_duplicate_part(
            "ATCGATCGATCG", "AATG", "GCTT", exclude_id=part.id
        )
        assert result is False
        
        # Check for duplicate without excluding
        result = check_duplicate_part("ATCGATCGATCG", "AATG", "GCTT")
        assert result is True


class TestValidateRequiredFields:
    """Tests for required fields validation (Requirement 10.2)."""
    
    def test_all_fields_present(self):
        """Test that validation passes when all fields are present."""
        validate_required_fields(
            name="Test Part",
            part_type="Coding",
            sequence="ATCGATCG",
            overhang_5prime="AATG",
            overhang_3prime="GCTT",
            lab_source="Test Lab",
            contributor="testuser"
        )
    
    def test_missing_name(self):
        """Test that missing name is detected."""
        with pytest.raises(ValidationError, match="Missing required field.*name"):
            validate_required_fields(
                name=None,
                part_type="Coding",
                sequence="ATCGATCG",
                overhang_5prime="AATG",
                overhang_3prime="GCTT",
                lab_source="Test Lab",
                contributor="testuser"
            )
    
    def test_empty_name(self):
        """Test that empty name is detected."""
        with pytest.raises(ValidationError, match="cannot be empty.*name"):
            validate_required_fields(
                name="   ",
                part_type="Coding",
                sequence="ATCGATCG",
                overhang_5prime="AATG",
                overhang_3prime="GCTT",
                lab_source="Test Lab",
                contributor="testuser"
            )
    
    def test_missing_multiple_fields(self):
        """Test that multiple missing fields are reported."""
        with pytest.raises(ValidationError, match="Missing required field"):
            validate_required_fields(
                name="Test Part",
                part_type=None,
                sequence=None,
                overhang_5prime="AATG",
                overhang_3prime="GCTT",
                lab_source="Test Lab",
                contributor="testuser"
            )
    
    def test_empty_lab_source(self):
        """Test that empty lab source is detected."""
        with pytest.raises(ValidationError, match="cannot be empty.*lab_source"):
            validate_required_fields(
                name="Test Part",
                part_type="Coding",
                sequence="ATCGATCG",
                overhang_5prime="AATG",
                overhang_3prime="GCTT",
                lab_source="",
                contributor="testuser"
            )


class TestValidatePartType:
    """Tests for part type validation."""
    
    def test_valid_part_types(self):
        """Test that valid part types pass validation."""
        valid_types = ['Coding', 'NonCodingPromoter', 'NonCodingTerminator']
        
        validate_part_type('Coding', valid_types)
        validate_part_type('NonCodingPromoter', valid_types)
        validate_part_type('NonCodingTerminator', valid_types)
    
    def test_invalid_part_type(self):
        """Test that invalid part types are rejected."""
        valid_types = ['Coding', 'NonCodingPromoter']
        
        with pytest.raises(ValidationError, match="Invalid part type"):
            validate_part_type('InvalidType', valid_types)


class TestValidatePartForUpload:
    """Tests for comprehensive part upload validation."""
    
    def test_valid_part_upload(self, temp_db):
        """Test that a valid part passes all validation checks."""
        validate_part_for_upload(
            name="Test Part",
            part_type="Coding",
            sequence="ATCGATCGATCG",
            overhang_5prime="AATG",
            overhang_3prime="GCTT",
            lab_source="Test Lab",
            contributor="testuser",
            valid_part_types=['Coding', 'NonCodingPromoter']
        )
    
    def test_invalid_sequence_rejected(self, temp_db):
        """Test that invalid sequences are rejected."""
        with pytest.raises(ValidationError, match="Invalid characters"):
            validate_part_for_upload(
                name="Test Part",
                part_type="Coding",
                sequence="ATCGXYZ",
                overhang_5prime="AATG",
                overhang_3prime="GCTT",
                lab_source="Test Lab",
                contributor="testuser",
                valid_part_types=['Coding']
            )
    
    def test_invalid_overhang_rejected(self, temp_db):
        """Test that invalid overhangs are rejected."""
        with pytest.raises(ValidationError, match="exactly 4 bases"):
            validate_part_for_upload(
                name="Test Part",
                part_type="Coding",
                sequence="ATCGATCGATCG",
                overhang_5prime="ATG",  # Only 3 bases
                overhang_3prime="GCTT",
                lab_source="Test Lab",
                contributor="testuser",
                valid_part_types=['Coding']
            )
    
    def test_duplicate_part_rejected(self, temp_db):
        """Test that duplicate parts are rejected."""
        # Create a part
        Part.create(
            name="Original Part",
            part_type="Coding",
            sequence="ATCGATCGATCG",
            overhang_5prime="AATG",
            overhang_3prime="GCTT",
            lab_source="Test Lab",
            contributor="testuser"
        )
        
        # Try to upload a duplicate
        with pytest.raises(ValidationError, match="already exists"):
            validate_part_for_upload(
                name="Duplicate Part",
                part_type="Coding",
                sequence="ATCGATCGATCG",
                overhang_5prime="AATG",
                overhang_3prime="GCTT",
                lab_source="Test Lab",
                contributor="testuser",
                valid_part_types=['Coding']
            )
    
    def test_skip_duplicate_check(self, temp_db):
        """Test that duplicate check can be skipped."""
        # Create a part
        Part.create(
            name="Original Part",
            part_type="Coding",
            sequence="ATCGATCGATCG",
            overhang_5prime="AATG",
            overhang_3prime="GCTT",
            lab_source="Test Lab",
            contributor="testuser"
        )
        
        # Should not raise when check_duplicates=False
        validate_part_for_upload(
            name="Duplicate Part",
            part_type="Coding",
            sequence="ATCGATCGATCG",
            overhang_5prime="AATG",
            overhang_3prime="GCTT",
            lab_source="Test Lab",
            contributor="testuser",
            valid_part_types=['Coding'],
            check_duplicates=False
        )


class TestHelperFunctions:
    """Tests for helper functions is_valid_dna_sequence and is_valid_overhang."""
    
    def test_is_valid_dna_sequence(self):
        """Test the boolean DNA sequence validator."""
        assert is_valid_dna_sequence("ATCGATCG") is True
        assert is_valid_dna_sequence("atcg") is True
        assert is_valid_dna_sequence("ATCGXYZ") is False
        assert is_valid_dna_sequence("") is False
        assert is_valid_dna_sequence("123") is False
    
    def test_is_valid_overhang(self):
        """Test the boolean overhang validator."""
        assert is_valid_overhang("ATCG") is True
        assert is_valid_overhang("atcg") is True
        assert is_valid_overhang("ATC") is False  # Too short
        assert is_valid_overhang("ATCGA") is False  # Too long
        assert is_valid_overhang("ATCX") is False  # Invalid character
        assert is_valid_overhang("") is False
