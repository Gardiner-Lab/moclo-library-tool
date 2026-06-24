"""
Part validation service for MoClo Library Tool.

This module provides validation functions for DNA sequences, overhangs,
duplicate parts, and required fields according to Requirements 10.2, 10.4, 10.7.
"""

from typing import Optional, Dict, Any, List
from app.models.parts_database import get_parts_database


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_dna_sequence(sequence: str) -> None:
    """
    Validate that a DNA sequence contains only valid bases (A, T, C, G).
    
    Args:
        sequence: DNA sequence to validate
        
    Raises:
        ValidationError: If sequence is invalid
        
    Requirements: 10.2
    """
    if not sequence:
        raise ValidationError("Sequence cannot be empty")
    
    # Check if all characters are valid DNA bases
    invalid_chars = set()
    for base in sequence.upper():
        if base not in 'ATCG':
            invalid_chars.add(base)
    
    if invalid_chars:
        raise ValidationError(
            f"Sequence must contain only A, T, C, G characters. "
            f"Invalid characters found: {', '.join(sorted(invalid_chars))}"
        )
    
    # Check minimum length (must accommodate overhangs)
    if len(sequence) < 8:
        raise ValidationError(
            "Sequence must be at least 8 bases long to accommodate overhangs"
        )


def validate_overhang_format(overhang: str, overhang_name: str = "overhang") -> None:
    """
    Validate that an overhang is exactly 4 bases and contains only valid DNA bases.
    
    Args:
        overhang: Overhang sequence to validate
        overhang_name: Name of the overhang for error messages (e.g., "5' overhang")
        
    Raises:
        ValidationError: If overhang format is invalid
        
    Requirements: 10.4
    """
    if not overhang:
        raise ValidationError(f"{overhang_name} cannot be empty")
    
    # Check length
    if len(overhang) != 4:
        raise ValidationError(
            f"{overhang_name} must be exactly 4 bases long. "
            f"Got {len(overhang)} bases: '{overhang}'"
        )
    
    # Check if all characters are valid DNA bases
    invalid_chars = set()
    for base in overhang.upper():
        if base not in 'ATCG':
            invalid_chars.add(base)
    
    if invalid_chars:
        raise ValidationError(
            f"{overhang_name} must contain only A, T, C, G characters. "
            f"Invalid characters found: {', '.join(sorted(invalid_chars))}"
        )


def check_duplicate_part(
    sequence: str,
    overhang_5prime: str,
    overhang_3prime: str,
    exclude_id: Optional[str] = None
) -> bool:
    """
    Check if a part with identical sequence and overhangs already exists.
    
    Args:
        sequence: DNA sequence to check
        overhang_5prime: 5' overhang sequence
        overhang_3prime: 3' overhang sequence
        exclude_id: Optional part ID to exclude from the check (for updates)
        
    Returns:
        True if a duplicate exists, False otherwise
        
    Requirements: 10.7
    """
    db = get_parts_database()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        if exclude_id:
            # Exclude a specific part ID (useful for updates)
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM parts 
                WHERE sequence = ? 
                AND overhang_5prime = ? 
                AND overhang_3prime = ?
                AND id != ?
                """,
                (sequence, overhang_5prime, overhang_3prime, exclude_id)
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM parts 
                WHERE sequence = ? 
                AND overhang_5prime = ? 
                AND overhang_3prime = ?
                """,
                (sequence, overhang_5prime, overhang_3prime)
            )
        
        result = cursor.fetchone()
        return result['count'] > 0


def validate_required_fields(
    name: Optional[str] = None,
    part_type: Optional[str] = None,
    sequence: Optional[str] = None,
    overhang_5prime: Optional[str] = None,
    overhang_3prime: Optional[str] = None,
    lab_source: Optional[str] = None,
    contributor: Optional[str] = None
) -> None:
    """
    Validate that all required fields are present and non-empty.
    
    Args:
        name: Part name
        part_type: Part type
        sequence: DNA sequence
        overhang_5prime: 5' overhang
        overhang_3prime: 3' overhang
        lab_source: Lab source
        contributor: Contributor username
        
    Raises:
        ValidationError: If any required field is missing or empty
        
    Requirements: 10.2
    """
    required_fields = {
        'name': name,
        'part_type': part_type,
        'sequence': sequence,
        'overhang_5prime': overhang_5prime,
        'overhang_3prime': overhang_3prime,
        'lab_source': lab_source,
        'contributor': contributor
    }
    
    missing_fields = []
    empty_fields = []
    
    for field_name, field_value in required_fields.items():
        if field_value is None:
            missing_fields.append(field_name)
        elif isinstance(field_value, str) and not field_value.strip():
            empty_fields.append(field_name)
    
    if missing_fields:
        raise ValidationError(
            f"Missing required field(s): {', '.join(missing_fields)}"
        )
    
    if empty_fields:
        raise ValidationError(
            f"Required field(s) cannot be empty: {', '.join(empty_fields)}"
        )


def validate_part_type(part_type: str, valid_types: List[str]) -> None:
    """
    Validate that a part type is one of the allowed types.
    
    Args:
        part_type: Part type to validate
        valid_types: List of valid part types
        
    Raises:
        ValidationError: If part type is not valid
    """
    if part_type not in valid_types:
        raise ValidationError(
            f"Invalid part type: '{part_type}'. "
            f"Must be one of: {', '.join(valid_types)}"
        )


def check_internal_restriction_sites(sequence: str) -> None:
    """
    Check for internal BsaI and BpiI restriction sites in a DNA sequence.
    
    BsaI recognition site: GGTCTC (and reverse complement GAGACC)
    BpiI recognition site: GAAGAC (and reverse complement GTCTTC)
    
    These sites should not be present internally in MoClo parts as they
    are used for assembly. Only the terminal overhangs should contain
    these sites.
    
    Args:
        sequence: DNA sequence to check
        
    Raises:
        ValidationError: If internal restriction sites are found
    """
    if not sequence:
        return
    
    seq_upper = sequence.upper()
    
    # BsaI recognition sites (forward and reverse complement)
    bsai_sites = ['GGTCTC', 'GAGACC']
    
    # BpiI recognition sites (forward and reverse complement)
    bpii_sites = ['GAAGAC', 'GTCTTC']
    
    # Check for BsaI sites
    bsai_positions = []
    for site in bsai_sites:
        pos = 0
        while True:
            pos = seq_upper.find(site, pos)
            if pos == -1:
                break
            bsai_positions.append((pos, site))
            pos += 1
    
    # Check for BpiI sites
    bpii_positions = []
    for site in bpii_sites:
        pos = 0
        while True:
            pos = seq_upper.find(site, pos)
            if pos == -1:
                break
            bpii_positions.append((pos, site))
            pos += 1
    
    # Build error message if sites found
    errors = []
    
    if bsai_positions:
        positions_str = ', '.join([f"{pos+1} ({site})" for pos, site in bsai_positions])
        errors.append(f"BsaI restriction site(s) found at position(s): {positions_str}")
    
    if bpii_positions:
        positions_str = ', '.join([f"{pos+1} ({site})" for pos, site in bpii_positions])
        errors.append(f"BpiI restriction site(s) found at position(s): {positions_str}")
    
    if errors:
        error_msg = "Part contains internal restriction sites that will interfere with MoClo assembly:\n"
        error_msg += "\n".join(errors)
        error_msg += "\n\nMoClo parts must not contain internal BsaI (GGTCTC/GAGACC) or BpiI (GAAGAC/GTCTTC) sites."
        raise ValidationError(error_msg)


def validate_part_for_upload(
    name: str,
    part_type: str,
    sequence: str,
    overhang_5prime: str,
    overhang_3prime: str,
    lab_source: str,
    contributor: str,
    valid_part_types: List[str],
    check_duplicates: bool = True
) -> None:
    """
    Comprehensive validation for part upload.
    
    This function performs all validation checks required for uploading a new part:
    - Required fields validation
    - DNA sequence validation
    - Overhang format validation
    - Part type validation
    - Internal restriction site check (BsaI, BpiI)
    - Duplicate part check
    
    Args:
        name: Part name
        part_type: Part type
        sequence: DNA sequence
        overhang_5prime: 5' overhang
        overhang_3prime: 3' overhang
        lab_source: Lab source
        contributor: Contributor username
        valid_part_types: List of valid part types
        check_duplicates: Whether to check for duplicate parts (default: True)
        
    Raises:
        ValidationError: If any validation fails
        
    Requirements: 10.2, 10.4, 10.7
    """
    # Validate required fields
    validate_required_fields(
        name=name,
        part_type=part_type,
        sequence=sequence,
        overhang_5prime=overhang_5prime,
        overhang_3prime=overhang_3prime,
        lab_source=lab_source,
        contributor=contributor
    )
    
    # Validate part type
    validate_part_type(part_type, valid_part_types)
    
    # Validate DNA sequence
    validate_dna_sequence(sequence)
    
    # Validate overhangs
    validate_overhang_format(overhang_5prime, "5' overhang")
    validate_overhang_format(overhang_3prime, "3' overhang")
    
    # Check for internal restriction sites (BsaI, BpiI)
    check_internal_restriction_sites(sequence)
    
    # Check for duplicates
    if check_duplicates:
        if check_duplicate_part(sequence, overhang_5prime, overhang_3prime):
            raise ValidationError(
                "A part with identical sequence and overhangs already exists in the library"
            )


def is_valid_dna_sequence(sequence: str) -> bool:
    """
    Check if a sequence contains only valid DNA bases (A, T, C, G).
    
    This is a non-throwing version of validate_dna_sequence for use in
    conditional logic.
    
    Args:
        sequence: DNA sequence to check
        
    Returns:
        True if valid, False otherwise
    """
    if not sequence:
        return False
    return all(base in 'ATCG' for base in sequence.upper())


def is_valid_overhang(overhang: str) -> bool:
    """
    Check if an overhang is exactly 4 valid DNA bases.
    
    This is a non-throwing version of validate_overhang_format for use in
    conditional logic.
    
    Args:
        overhang: Overhang sequence to check
        
    Returns:
        True if valid, False otherwise
    """
    if not overhang or len(overhang) != 4:
        return False
    return all(base in 'ATCG' for base in overhang.upper())
