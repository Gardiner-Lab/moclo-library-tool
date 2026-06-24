"""
Assembly service for creating cassettes from MoClo parts.

This service provides functions to assemble compatible parts into cassettes,
validate assemblies, and generate appropriate error messages for invalid assemblies.
"""

from typing import List, Dict, Any, Optional
from app.models.part import Part
from app.models.cassette import Cassette
from app.services.compatibility import validate_assembly


class AssemblyError(Exception):
    """Exception raised when assembly validation fails."""
    pass


def assemble_parts(parts: List[Part]) -> str:
    """
    Assemble a list of compatible parts into a complete DNA sequence.
    
    The assembly algorithm works as follows:
    1. Validate that parts form a valid assembly chain
    2. Start with the first part's 5' overhang + sequence
    3. For each subsequent part, add the overhang scar (4bp) and then the part sequence
    4. End with the last part's 3' overhang
    
    In MoClo assembly, when BsaI cuts and parts are ligated, the 4bp overhangs
    form scars that remain in the final assembled sequence. These scars are the
    junction points between parts. The cassette retains the 5' overhang of the
    first part and the 3' overhang of the last part for insertion into backbones.
    
    Args:
        parts: Ordered list of parts to assemble (must be at least 2 parts)
        
    Returns:
        Complete assembled DNA sequence as a string (including terminal overhangs)
        
    Raises:
        AssemblyError: If parts are incompatible or validation fails
        
    Example:
        >>> part1 = Part(..., overhang_5prime='AAAA', sequence='TTTTGGGG', overhang_3prime='CCCC', ...)
        >>> part2 = Part(..., overhang_5prime='CCCC', sequence='GGGGTTTT', overhang_3prime='GGGG', ...)
        >>> assembled = assemble_parts([part1, part2])
        >>> assembled
        'AAAATTTTGGGGCCCCGGGGTTTTGGGG'
        # Note: Starts with part1's 5' overhang, includes scar, ends with part2's 3' overhang
    """
    # Validate the assembly
    validation = validate_assembly(parts)
    
    if not validation['valid']:
        raise AssemblyError(validation['error'])
    
    # Start with the first part's 5' overhang and sequence
    assembled_sequence = parts[0].overhang_5prime + parts[0].sequence
    
    # Add each subsequent part with its overhang scar
    # The overhang scar is the 4bp junction that forms when parts are ligated
    for i in range(1, len(parts)):
        part = parts[i]
        # Add the overhang scar (the 5' overhang of this part, which matches
        # the 3' overhang of the previous part)
        overhang_scar = part.overhang_5prime
        assembled_sequence += overhang_scar
        # Add the part sequence
        assembled_sequence += part.sequence
    
    # Add the last part's 3' overhang
    assembled_sequence += parts[-1].overhang_3prime
    
    return assembled_sequence


def create_cassette(
    name: str,
    owner_id: str,
    parts: List[Part]
) -> Cassette:
    """
    Create a new cassette from a list of parts.
    
    This function validates the parts, assembles them into a sequence,
    analyzes translation for coding sequences, and creates a cassette record.
    
    Args:
        name: Name for the cassette
        owner_id: ID of the user creating the cassette
        parts: Ordered list of parts to assemble
        
    Returns:
        Created Cassette instance with translation analysis
        
    Raises:
        AssemblyError: If parts are incompatible or validation fails
        ValueError: If cassette creation fails (e.g., invalid name)
        
    Example:
        >>> part1 = Part.get_by_id('part-id-1')
        >>> part2 = Part.get_by_id('part-id-2')
        >>> cassette = create_cassette('My Construct', 'user-id', [part1, part2])
        >>> print(cassette.name)
        'My Construct'
    """
    # Assemble the parts (this also validates compatibility)
    try:
        assembled_sequence = assemble_parts(parts)
    except AssemblyError:
        # Re-raise assembly errors as-is
        raise
    
    # Extract part IDs
    part_ids = [part.id for part in parts]
    
    # Analyze translation for coding sequences
    from app.services.translation import analyze_coding_sequence, get_part_boundaries_from_cassette
    
    part_boundaries = get_part_boundaries_from_cassette(parts, assembled_sequence)
    translation_analysis = analyze_coding_sequence(assembled_sequence, part_boundaries)
    
    # Create the cassette
    try:
        cassette = Cassette.create(
            name=name,
            owner_id=owner_id,
            part_ids=part_ids,
            assembled_sequence=assembled_sequence
        )
        
        # Store translation analysis as an attribute (not persisted to DB, calculated on demand)
        cassette.translation_analysis = translation_analysis
        
        return cassette
    except ValueError as e:
        # Re-raise validation errors from Cassette.create
        raise ValueError(f"Failed to create cassette: {str(e)}")


def validate_parts_for_assembly(part_ids: List[str]) -> Dict[str, Any]:
    """
    Validate that a list of part IDs can be assembled into a cassette.
    
    This function checks:
    1. All part IDs exist in the database
    2. There are at least 2 parts
    3. Parts form a valid assembly chain (compatible overhangs)
    
    Args:
        part_ids: List of part IDs to validate
        
    Returns:
        Dictionary with validation result:
        - 'valid': Boolean indicating if assembly is valid
        - 'error': Error message if invalid, empty string if valid
        - 'parts': List of Part objects if all IDs are valid, None otherwise
        - 'assembled_length': Expected length of assembled sequence if valid
        
    Example:
        >>> result = validate_parts_for_assembly(['id1', 'id2', 'id3'])
        >>> if result['valid']:
        ...     print(f"Assembly will be {result['assembled_length']} bases")
        ... else:
        ...     print(f"Error: {result['error']}")
    """
    # Check minimum number of parts
    if len(part_ids) < 2:
        return {
            'valid': False,
            'error': 'Assembly requires at least 2 parts',
            'parts': None,
            'assembled_length': 0
        }
    
    # Retrieve all parts
    parts = []
    for part_id in part_ids:
        part = Part.get_by_id(part_id)
        if part is None:
            return {
                'valid': False,
                'error': f'Part with ID {part_id} not found',
                'parts': None,
                'assembled_length': 0
            }
        parts.append(part)
    
    # Validate assembly compatibility
    validation = validate_assembly(parts)
    
    if not validation['valid']:
        return {
            'valid': False,
            'error': validation['error'],
            'parts': parts,
            'assembled_length': 0
        }
    
    # Calculate expected assembled length
    # First part contributes full length
    # Each subsequent part contributes: 4bp (overhang scar) + full part length
    assembled_length = len(parts[0].sequence)
    for i in range(1, len(parts)):
        assembled_length += 4 + len(parts[i].sequence)  # overhang scar + part sequence
    
    return {
        'valid': True,
        'error': '',
        'parts': parts,
        'assembled_length': assembled_length
    }


def get_assembly_preview(parts: List[Part]) -> Dict[str, Any]:
    """
    Generate a preview of what the assembly would look like without creating it.
    
    This is useful for UI previews and validation before committing to create
    a cassette.
    
    Args:
        parts: Ordered list of parts to preview
        
    Returns:
        Dictionary with preview information:
        - 'valid': Boolean indicating if assembly is valid
        - 'error': Error message if invalid, empty string if valid
        - 'sequence': Assembled sequence if valid, empty string otherwise
        - 'length': Length of assembled sequence
        - 'part_count': Number of parts
        - 'junctions': List of junction information between parts
        
    Example:
        >>> preview = get_assembly_preview([part1, part2, part3])
        >>> if preview['valid']:
        ...     print(f"Assembly: {preview['length']} bp from {preview['part_count']} parts")
        ...     for junction in preview['junctions']:
        ...         print(f"  {junction['part1_name']} -> {junction['part2_name']}: {junction['overhang']}")
    """
    # Validate assembly
    validation = validate_assembly(parts)
    
    if not validation['valid']:
        return {
            'valid': False,
            'error': validation['error'],
            'sequence': '',
            'length': 0,
            'part_count': len(parts),
            'junctions': []
        }
    
    # Assemble the sequence
    try:
        assembled_sequence = assemble_parts(parts)
    except AssemblyError as e:
        return {
            'valid': False,
            'error': str(e),
            'sequence': '',
            'length': 0,
            'part_count': len(parts),
            'junctions': []
        }
    
    # Generate junction information
    junctions = []
    for i in range(len(parts) - 1):
        part1 = parts[i]
        part2 = parts[i + 1]
        junctions.append({
            'part1_name': part1.name,
            'part1_id': part1.id,
            'part2_name': part2.name,
            'part2_id': part2.id,
            'overhang': part1.overhang_3prime,
            'position': i
        })
    
    return {
        'valid': True,
        'error': '',
        'sequence': assembled_sequence,
        'length': len(assembled_sequence),
        'part_count': len(parts),
        'junctions': junctions
    }


def disassemble_cassette(cassette: Cassette) -> List[Part]:
    """
    Retrieve the parts that make up a cassette in order.
    
    Args:
        cassette: Cassette to disassemble
        
    Returns:
        Ordered list of Part objects that make up the cassette
        
    Raises:
        ValueError: If any part ID in the cassette is not found
        
    Example:
        >>> cassette = Cassette.get_by_id('cassette-id')
        >>> parts = disassemble_cassette(cassette)
        >>> for part in parts:
        ...     print(f"  {part.name} ({part.part_type})")
    """
    parts = []
    for part_id in cassette.part_ids:
        part = Part.get_by_id(part_id)
        if part is None:
            raise ValueError(f"Part with ID {part_id} not found in database")
        parts.append(part)
    
    return parts


def verify_cassette_assembly(cassette: Cassette) -> Dict[str, Any]:
    """
    Verify that a cassette's assembled sequence matches what would be generated
    from its component parts.
    
    This is useful for data integrity checks and debugging.
    
    Args:
        cassette: Cassette to verify
        
    Returns:
        Dictionary with verification result:
        - 'valid': Boolean indicating if cassette is valid
        - 'error': Error message if invalid, empty string if valid
        - 'expected_sequence': What the sequence should be
        - 'actual_sequence': What the sequence is in the cassette
        - 'match': Boolean indicating if sequences match
        
    Example:
        >>> cassette = Cassette.get_by_id('cassette-id')
        >>> verification = verify_cassette_assembly(cassette)
        >>> if not verification['valid']:
        ...     print(f"Cassette integrity error: {verification['error']}")
    """
    try:
        # Get the parts
        parts = disassemble_cassette(cassette)
        
        # Assemble them
        expected_sequence = assemble_parts(parts)
        
        # Compare with stored sequence
        actual_sequence = cassette.assembled_sequence
        match = expected_sequence == actual_sequence
        
        if not match:
            error = (
                f"Sequence mismatch: expected {len(expected_sequence)} bases, "
                f"got {len(actual_sequence)} bases"
            )
        else:
            error = ''
        
        return {
            'valid': match,
            'error': error,
            'expected_sequence': expected_sequence,
            'actual_sequence': actual_sequence,
            'match': match
        }
    
    except (ValueError, AssemblyError) as e:
        return {
            'valid': False,
            'error': str(e),
            'expected_sequence': '',
            'actual_sequence': cassette.assembled_sequence,
            'match': False
        }
