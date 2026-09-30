"""
Compatibility checker service for MoClo parts.

This service provides functions to check if parts are compatible for assembly
based on their overhang sequences, find compatible parts, and validate
assembly orders.
"""

from typing import List, Dict, Optional, Tuple
from app.models.part import Part


_COMPLEMENT = {
    'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C',
    'R': 'Y', 'Y': 'R', 'S': 'S', 'W': 'W',
    'K': 'M', 'M': 'K', 'B': 'V', 'V': 'B',
    'D': 'H', 'H': 'D', 'N': 'N'
}


def reverse_complement(sequence: str) -> str:
    """
    Return the reverse complement of a DNA sequence.

    Unknown characters are passed through unchanged so that malformed input
    fails later validation rather than silently corrupting here.
    """
    return ''.join(_COMPLEMENT.get(base, base) for base in reversed(sequence.upper()))


def oriented_overhangs(part: Part, orientation: str = 'forward') -> Tuple[str, str]:
    """
    Return the (5', 3') overhangs a part presents to the assembly in a given
    orientation.

    A MoClo Level 1 transcription unit can be cloned into a position acceptor in
    reverse orientation (e.g. pICH47802 = "Position 1 Rv"). When placed reverse,
    the part's whole sequence is reverse-complemented in the final construct, so
    the fusion sites it presents are swapped and reverse-complemented:
    what it stores as its 5' overhang becomes rc(3') on the right, and its 3'
    overhang becomes rc(5') on the left.

    Args:
        part: The part
        orientation: 'forward' (as stored) or 'reverse' (reverse-complemented)

    Returns:
        Tuple of (presented_5prime, presented_3prime) as uppercase 4bp strings.
    """
    o5 = (part.overhang_5prime or '').upper()
    o3 = (part.overhang_3prime or '').upper()
    if orientation == 'reverse':
        return (reverse_complement(o3), reverse_complement(o5))
    return (o5, o3)


def compatibility_orientation(part1: Part, part2: Part, part1_orientation: str = 'forward') -> Optional[str]:
    """
    Determine whether part2 can follow part1, and in which orientation.

    part1 is assumed to already be placed in ``part1_orientation``. part2 can be
    joined after it if part2 (in some orientation) presents a 5' overhang equal
    to the 3' overhang part1 presents. part2 is tried in forward orientation
    first, then reverse.

    Args:
        part1: The part already placed (its presented 3' overhang is the junction)
        part2: The candidate part to place after part1
        part1_orientation: Orientation part1 is placed in ('forward'/'reverse')

    Returns:
        'forward' or 'reverse' if part2 can follow part1 in that orientation,
        or None if it cannot be joined in either orientation.
    """
    junction = oriented_overhangs(part1, part1_orientation)[1]  # part1's presented 3'
    for orientation in ('forward', 'reverse'):
        if oriented_overhangs(part2, orientation)[0] == junction:
            return orientation
    return None


def are_compatible(part1: Part, part2: Part) -> bool:
    """
    Check if two parts are compatible for assembly, in either orientation.
    
    Two parts are compatible if part1's presented 3' overhang matches part2's
    presented 5' overhang for some orientation of part2 (forward or reverse).
    part1 is treated as forward.
    
    Args:
        part1: First part (will be placed before part2)
        part2: Second part (will be placed after part1)
        
    Returns:
        True if part2 can be placed after part1 in some orientation.
        
    Example:
        >>> part1 = Part(..., overhang_3prime='ATCG', ...)
        >>> part2 = Part(..., overhang_5prime='ATCG', ...)
        >>> are_compatible(part1, part2)
        True
    """
    return compatibility_orientation(part1, part2, 'forward') is not None


def find_compatible_parts(target_part: Part, all_parts: List[Part]) -> Dict[str, List[Part]]:
    """
    Find all parts compatible with a given target part.
    
    Returns parts that can be placed before the target (their 3' overhang
    matches the target's 5' overhang) and parts that can be placed after
    the target (their 5' overhang matches the target's 3' overhang).
    
    Args:
        target_part: The part to find compatible parts for
        all_parts: List of all available parts to check
        
    Returns:
        Dictionary with two keys:
        - 'before': List of parts that can be placed before the target
        - 'after': List of parts that can be placed after the target
        
    Example:
        >>> target = Part(..., overhang_5prime='AAAA', overhang_3prime='TTTT', ...)
        >>> part_before = Part(..., overhang_3prime='AAAA', ...)
        >>> part_after = Part(..., overhang_5prime='TTTT', ...)
        >>> result = find_compatible_parts(target, [part_before, part_after])
        >>> len(result['before'])  # Contains part_before
        1
        >>> len(result['after'])   # Contains part_after
        1
    """
    before = []
    after = []
    
    for part in all_parts:
        # Skip the target part itself
        if part.id == target_part.id:
            continue
        
        # The target is held in its stored (forward) orientation; only the
        # candidate part is allowed to flip. This keeps the result target-centric:
        # "which parts can attach to this part as it is?"
        target_5 = oriented_overhangs(target_part, 'forward')[0]
        target_3 = oriented_overhangs(target_part, 'forward')[1]

        # Candidate can be placed BEFORE the target if, in some orientation, the
        # candidate's presented 3' overhang equals the target's 5' overhang.
        if any(oriented_overhangs(part, o)[1] == target_5 for o in ('forward', 'reverse')):
            before.append(part)

        # Candidate can be placed AFTER the target if, in some orientation, the
        # candidate's presented 5' overhang equals the target's 3' overhang.
        if any(oriented_overhangs(part, o)[0] == target_3 for o in ('forward', 'reverse')):
            after.append(part)
    
    return {
        'before': before,
        'after': after
    }


def resolve_orientations(parts: List[Part]) -> Optional[List[str]]:
    """
    Resolve the orientation of each part in an ordered assembly chain.

    The first part anchors in forward orientation. Each subsequent part is
    oriented (forward or reverse) so its presented 5' overhang matches the
    running junction (the presented 3' overhang of the previous part).

    Args:
        parts: Ordered list of parts

    Returns:
        List of orientation strings ('forward'/'reverse'), one per part, or
        None if any adjacent pair cannot be joined in either orientation.
    """
    if not parts:
        return []
    if len(parts) == 1:
        return ['forward']

    # The first part is an anchor whose orientation is free: a valid chain may
    # require it reversed (e.g. a Position-1 reverse cassette that presents the
    # canonical TGCC/GCAA boundaries only when flipped). Try forward first, then
    # reverse, and return the first anchor orientation that lets the whole chain
    # connect.
    for anchor in ('forward', 'reverse'):
        orientations = [anchor]
        ok = True
        for i in range(1, len(parts)):
            chosen = compatibility_orientation(parts[i - 1], parts[i], orientations[i - 1])
            if chosen is None:
                ok = False
                break
            orientations.append(chosen)
        if ok:
            return orientations
    return None


def validate_assembly(parts: List[Part]) -> Dict[str, any]:
    """
    Validate that an ordered list of parts can be assembled.
    
    Checks that:
    1. There are at least 2 parts
    2. Each adjacent pair of parts has compatible overhangs
    
    Args:
        parts: Ordered list of parts to validate for assembly
        
    Returns:
        Dictionary with validation result:
        - 'valid': Boolean indicating if assembly is valid
        - 'error': Error message if invalid, empty string if valid
        - 'incompatible_pair': Tuple of (index1, index2) for first incompatible
          pair, or None if valid
        
    Example:
        >>> part1 = Part(..., overhang_3prime='ATCG', ...)
        >>> part2 = Part(..., overhang_5prime='ATCG', overhang_3prime='GCTA', ...)
        >>> part3 = Part(..., overhang_5prime='GCTA', ...)
        >>> result = validate_assembly([part1, part2, part3])
        >>> result['valid']
        True
        >>> result['error']
        ''
    """
    # Check minimum number of parts
    if len(parts) < 2:
        return {
            'valid': False,
            'error': 'Assembly requires at least 2 parts',
            'incompatible_pair': None,
            'orientations': None
        }
    
    # Resolve orientations for the whole chain. The first part is a free anchor
    # (tried both orientations); each subsequent part is placed forward or
    # reverse-complemented so its 5' fusion site matches the running junction.
    orientations = resolve_orientations(parts)
    if orientations is not None:
        return {
            'valid': True,
            'error': '',
            'incompatible_pair': None,
            'orientations': orientations
        }

    # The chain cannot be made contiguous in any anchor orientation. Report the
    # first pair that fails to connect, using the forward-anchor walk (the most
    # intuitive framing for the error message).
    walk = ['forward']
    for i in range(len(parts) - 1):
        chosen = compatibility_orientation(parts[i], parts[i + 1], walk[i])
        if chosen is None:
            presented_3 = oriented_overhangs(parts[i], walk[i])[1]
            error_msg = (
                f"Parts at positions {i} and {i+1} have incompatible overhangs: "
                f"part '{parts[i].name}' presents 3' overhang '{presented_3}' "
                f"but part '{parts[i+1].name}' has 5' overhang '{parts[i+1].overhang_5prime}' "
                f"(3' '{parts[i+1].overhang_3prime}') and matches in neither orientation"
            )
            return {
                'valid': False,
                'error': error_msg,
                'incompatible_pair': (i, i + 1),
                'orientations': None
            }
        walk.append(chosen)

    # Fallback (should not normally reach here).
    return {
        'valid': False,
        'error': 'Parts cannot be assembled into a contiguous chain in any orientation',
        'incompatible_pair': None,
        'orientations': None
    }


def get_compatibility_info(part1: Part, part2: Part) -> Dict[str, any]:
    """
    Get detailed compatibility information between two parts.
    
    Args:
        part1: First part
        part2: Second part
        
    Returns:
        Dictionary with compatibility details:
        - 'compatible': Boolean indicating if parts are compatible
        - 'part1_3prime': 3' overhang of part1
        - 'part2_5prime': 5' overhang of part2
        - 'match': Boolean indicating if overhangs match
        - 'message': Human-readable message about compatibility
        
    Example:
        >>> part1 = Part(..., name='PartA', overhang_3prime='ATCG', ...)
        >>> part2 = Part(..., name='PartB', overhang_5prime='ATCG', ...)
        >>> info = get_compatibility_info(part1, part2)
        >>> info['compatible']
        True
        >>> info['message']
        "Parts are compatible: PartA (3': ATCG) can be joined with PartB (5': ATCG)"
    """
    part2_orientation = compatibility_orientation(part1, part2, 'forward')
    compatible = part2_orientation is not None
    part2_presented_5 = oriented_overhangs(part2, part2_orientation)[0] if compatible else part2.overhang_5prime
    
    if compatible:
        orient_note = '' if part2_orientation == 'forward' else ' (in reverse orientation)'
        message = (
            f"Parts are compatible: {part1.name} (3': {part1.overhang_3prime}) "
            f"can be joined with {part2.name} (5': {part2_presented_5}){orient_note}"
        )
    else:
        message = (
            f"Parts are incompatible: {part1.name} (3': {part1.overhang_3prime}) "
            f"cannot be joined with {part2.name} (5': {part2.overhang_5prime} / "
            f"3': {part2.overhang_3prime}) in either orientation"
        )
    
    return {
        'compatible': compatible,
        'part1_3prime': part1.overhang_3prime,
        'part2_5prime': part2.overhang_5prime,
        'part2_orientation': part2_orientation,
        'match': compatible,
        'message': message
    }
