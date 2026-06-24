"""
Compatibility checker service for MoClo parts.

This service provides functions to check if parts are compatible for assembly
based on their overhang sequences, find compatible parts, and validate
assembly orders.
"""

from typing import List, Dict, Optional
from app.models.part import Part


def are_compatible(part1: Part, part2: Part) -> bool:
    """
    Check if two parts are compatible for assembly.
    
    Two parts are compatible if the 3' overhang of part1 matches
    the 5' overhang of part2, allowing them to be joined in that order.
    
    Args:
        part1: First part (will be placed before part2)
        part2: Second part (will be placed after part1)
        
    Returns:
        True if parts are compatible (part1 can be placed before part2),
        False otherwise
        
    Example:
        >>> part1 = Part(..., overhang_3prime='ATCG', ...)
        >>> part2 = Part(..., overhang_5prime='ATCG', ...)
        >>> are_compatible(part1, part2)
        True
    """
    return part1.overhang_3prime == part2.overhang_5prime


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
        
        # Check if this part can be placed before the target
        if part.overhang_3prime == target_part.overhang_5prime:
            before.append(part)
        
        # Check if this part can be placed after the target
        if target_part.overhang_3prime == part.overhang_5prime:
            after.append(part)
    
    return {
        'before': before,
        'after': after
    }


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
            'incompatible_pair': None
        }
    
    # Check each adjacent pair for compatibility
    for i in range(len(parts) - 1):
        part1 = parts[i]
        part2 = parts[i + 1]
        
        if not are_compatible(part1, part2):
            error_msg = (
                f"Parts at positions {i} and {i+1} have incompatible overhangs: "
                f"part '{part1.name}' has 3' overhang '{part1.overhang_3prime}' "
                f"but part '{part2.name}' has 5' overhang '{part2.overhang_5prime}'"
            )
            return {
                'valid': False,
                'error': error_msg,
                'incompatible_pair': (i, i + 1)
            }
    
    # All checks passed
    return {
        'valid': True,
        'error': '',
        'incompatible_pair': None
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
    compatible = are_compatible(part1, part2)
    
    if compatible:
        message = (
            f"Parts are compatible: {part1.name} (3': {part1.overhang_3prime}) "
            f"can be joined with {part2.name} (5': {part2.overhang_5prime})"
        )
    else:
        message = (
            f"Parts are incompatible: {part1.name} (3': {part1.overhang_3prime}) "
            f"cannot be joined with {part2.name} (5': {part2.overhang_5prime})"
        )
    
    return {
        'compatible': compatible,
        'part1_3prime': part1.overhang_3prime,
        'part2_5prime': part2.overhang_5prime,
        'match': part1.overhang_3prime == part2.overhang_5prime,
        'message': message
    }
