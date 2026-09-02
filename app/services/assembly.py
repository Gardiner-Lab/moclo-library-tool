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
    (sticky ends) anneal to form scars that remain in the final assembled
    sequence. Because the two annealing sticky ends are complementary halves of
    the SAME 4bp junction, each scar appears exactly ONCE in the ligated product.

    Each stored part sequence already includes its own 5' overhang at the start
    and its 3' overhang at the end (as extracted by the GenBank parser). Two
    compatible parts share an overhang: part1's 3' overhang == part2's 5' overhang.
    To ligate them we must overlap that shared overhang so it is not duplicated:
    we take part1 in full, then append each subsequent part with its leading
    (shared) 5' overhang removed.

    Args:
        parts: Ordered list of parts to assemble (must be at least 2 parts)
        
    Returns:
        Complete assembled DNA sequence as a string (including terminal overhangs)
        
    Raises:
        AssemblyError: If parts are incompatible or validation fails
        
    Example:
        >>> # sequences include their own overhangs (5' at start, 3' at end)
        >>> part1 = Part(..., overhang_5prime='AAAA', sequence='AAAAxxxxCCCC', overhang_3prime='CCCC', ...)
        >>> part2 = Part(..., overhang_5prime='CCCC', sequence='CCCCyyyyGGGG', overhang_3prime='GGGG', ...)
        >>> assemble_parts([part1, part2])
        'AAAAxxxxCCCCyyyyGGGG'
        # The shared 'CCCC' scar appears once at the junction, not twice.
    """
    # Validate the assembly
    validation = validate_assembly(parts)
    
    if not validation['valid']:
        raise AssemblyError(validation['error'])
    
    # Start with the first part's full sequence (already includes its 5' and 3' overhangs)
    assembled_sequence = parts[0].sequence
    
    # Add each subsequent part, overlapping the shared 4bp overhang scar.
    # The previous part already ends with the shared overhang (its 3' overhang),
    # and this part's sequence begins with that same overhang (its 5' overhang).
    # We strip this part's leading overhang so the scar is not duplicated.
    for i in range(1, len(parts)):
        part = parts[i]
        # Strip this part's leading 4bp 5' overhang, which is the shared scar
        # already contributed by the previous part's 3' overhang. This prevents
        # the sticky-end junction from being duplicated in the ligated product.
        assembled_sequence += part.sequence[4:]
    
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
    The MoClo level is determined from the source parts:
    - If parts are Level 0, the cassette is Level 1
    - If parts are Level 1, the cassette is Level 2
    
    Translation data from Level 0 parts is preserved through the hierarchy.
    
    Args:
        name: Name for the cassette
        owner_id: ID of the user creating the cassette
        parts: Ordered list of parts to assemble
        
    Returns:
        Created Cassette instance with translation analysis
        
    Raises:
        AssemblyError: If parts are incompatible or validation fails
        ValueError: If cassette creation fails (e.g., invalid name)
    """
    # Assemble the parts (this also validates compatibility)
    try:
        assembled_sequence = assemble_parts(parts)
    except AssemblyError:
        # Re-raise assembly errors as-is
        raise
    
    # Extract part IDs
    part_ids = [part.id for part in parts]
    
    # Determine MoClo level from parts
    cassette_level = _determine_cassette_level(parts)
    
    # Capture part metadata snapshot at assembly time
    # This preserves type, name, overhangs, intron info even if parts are later modified/deleted
    parts_metadata = _capture_parts_metadata(parts, assembled_sequence)
    
    # Analyze translation for coding sequences
    from app.services.translation import analyze_coding_sequence, get_part_boundaries_from_cassette
    
    part_boundaries = get_part_boundaries_from_cassette(parts, assembled_sequence)
    translation_analysis = analyze_coding_sequence(assembled_sequence, part_boundaries)
    
    # Create the cassette with level and translation data
    try:
        cassette = Cassette.create(
            name=name,
            owner_id=owner_id,
            part_ids=part_ids,
            assembled_sequence=assembled_sequence,
            level=cassette_level,
            translation_data=translation_analysis,
            parts_metadata=parts_metadata
        )
        
        # Also attach as a transient attribute for immediate access
        cassette.translation_analysis = translation_analysis
        
        return cassette
    except ValueError as e:
        # Re-raise validation errors from Cassette.create
        raise ValueError(f"Failed to create cassette: {str(e)}")


def recompute_cassette_translation(cassette) -> Optional[Dict[str, Any]]:
    """
    Rebuild a cassette's persisted translation analysis and part-metadata
    snapshot from its current Level 0 parts.

    Call this after a source part changes in a way that affects whether a
    coding region is present or an intron must be spliced (for example its
    part type is edited). Returns the new translation analysis, or None when
    the cassette's parts can no longer be loaded.
    """
    from app.models.part import Part
    from app.services.translation import (
        analyze_coding_sequence,
        get_part_boundaries_from_cassette,
    )

    parts = [p for p in (Part.get_by_id(pid) for pid in (cassette.part_ids or [])) if p]
    if not parts:
        return None

    parts_metadata = _capture_parts_metadata(parts, cassette.assembled_sequence)
    boundaries = get_part_boundaries_from_cassette(parts, cassette.assembled_sequence)
    translation = analyze_coding_sequence(cassette.assembled_sequence, boundaries)
    cassette.update_analysis(translation_data=translation, parts_metadata=parts_metadata)
    return translation


def _determine_cassette_level(parts: List[Part]) -> str:
    """
    Determine the MoClo level of a cassette based on its source parts.
    
    In MoClo hierarchy:
    - Level 0 parts → assembled into Level 1 cassettes (transcription units)
    - Level 1 parts → assembled into Level 2 cassettes (multigene constructs)
    - If part levels are mixed or unset, default to Level 1
    
    Args:
        parts: List of parts being assembled
        
    Returns:
        String level ('1', '2', '3', etc.)
    """
    part_levels = []
    for part in parts:
        if part.level:
            try:
                part_levels.append(int(part.level))
            except (ValueError, TypeError):
                pass
    
    if not part_levels:
        # No levels set on parts, default to Level 1 (parts are assumed Level 0)
        return '1'
    
    # The cassette level is one above the source part level
    max_part_level = max(part_levels)
    return str(max_part_level + 1)


def _capture_parts_metadata(parts: List[Part], assembled_sequence: str) -> List[Dict[str, Any]]:
    """
    Capture a snapshot of part metadata at assembly time.
    
    This preserves key information about each part (type, name, overhangs,
    sequence positions, intron annotations) so that cassette details remain
    available even if the original parts are later modified or deleted.
    
    For coding parts, the translation of the coding sequence is included.
    For parts with intron annotations, those are preserved as well.
    
    Args:
        parts: Ordered list of Part objects being assembled
        assembled_sequence: The final assembled sequence
        
    Returns:
        List of dictionaries, one per part, with metadata snapshot
    """
    import json
    import re
    from app.services.translation import translate_sequence, find_start_codons
    
    metadata = []
    current_pos = 0
    
    for i, part in enumerate(parts):
        # Calculate position in assembled sequence.
        # The assembled sequence overlaps the shared 4bp overhang between parts,
        # so each part after the first contributes its length minus the 4bp
        # leading overhang (which is shared with the previous part's 3' overhang).
        if i == 0:
            part_length = len(part.sequence)
        else:
            part_length = len(part.sequence) - 4  # leading shared overhang overlaps previous part
        
        part_start = current_pos
        part_end = current_pos + part_length
        
        entry = {
            'part_id': part.id,
            'part_name': part.name,
            'part_type': part.part_type,
            'overhang_5prime': part.overhang_5prime,
            'overhang_3prime': part.overhang_3prime,
            'sequence_length': len(part.sequence),
            'position_start': part_start,
            'position_end': part_end,
            'level': part.level,
            'source_vector': part.plasmid_id if hasattr(part, 'plasmid_id') else None,
            'size': part.size if hasattr(part, 'size') else None,
            'lab_source': part.lab_source if hasattr(part, 'lab_source') else None,
            'contributor': part.contributor if hasattr(part, 'contributor') else None,
            'description': part.description,
            'is_coding': part.part_type in ('Coding', 'ExpressionCassette'),
        }

        # For coding parts (a plain CDS or an expression cassette), record the
        # translation of the part's own coding sequence, spliced when the part
        # carries introns, so a construct can report per-part protein output.
        if entry['is_coding']:
            try:
                from app.services.translation import (
                    analyze_coding_sequence,
                    get_part_boundaries_from_cassette,
                )
                pb = get_part_boundaries_from_cassette([part], part.sequence)
                t = analyze_coding_sequence(part.sequence, pb)
                protein = t.get('protein_sequence_spliced') or t.get('protein_sequence')
                entry['coding_translation'] = {
                    'protein_sequence': protein,
                    'protein_length': len((protein or '').rstrip('*')),
                    'has_stop_codon': '*' in (protein or ''),
                    'requires_splicing': t.get('requires_splicing', False),
                    'intron_count': len(t.get('intron_positions') or []),
                }
                if not t.get('has_coding'):
                    entry['coding_translation']['warning'] = 'No ATG start codon found in coding sequence'
            except Exception:  # noqa: BLE001
                part_seq = part.sequence.upper()
                start_codons = find_start_codons(part_seq)
                if start_codons:
                    protein = translate_sequence(part_seq, start_codons[0])
                    entry['coding_translation'] = {
                        'protein_sequence': protein,
                        'start_codon_position': start_codons[0],
                        'protein_length': len(protein.rstrip('*')),
                        'has_stop_codon': '*' in protein,
                    }
                else:
                    entry['coding_translation'] = {
                        'protein_sequence': None,
                        'protein_length': 0,
                        'has_stop_codon': False,
                        'warning': 'No ATG start codon found in coding sequence',
                    }
        
        # Extract intron annotations from comments if present
        intron_annotations = []
        if hasattr(part, 'comments') and part.comments:
            match = re.search(r'INTRON_ANNOTATIONS:\s*(\[.*?\])', part.comments, re.DOTALL)
            if match:
                try:
                    intron_annotations = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        
        if intron_annotations:
            entry['intron_annotations'] = intron_annotations
        
        # Mark intron parts explicitly
        if part.part_type == 'NonCodingIntron':
            entry['is_intron'] = True
        
        metadata.append(entry)
        current_pos = part_end
    
    return metadata


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
    
    # Calculate expected assembled length.
    # Each stored part sequence already includes its own 5' and 3' overhangs.
    # When parts ligate, the shared 4bp overhang between adjacent parts overlaps
    # (appears once), so each part after the first contributes its length minus 4.
    assembled_length = len(parts[0].sequence)
    for i in range(1, len(parts)):
        assembled_length += len(parts[i].sequence) - 4  # shared overhang overlaps previous part
    
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
