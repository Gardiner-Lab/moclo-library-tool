"""
Backbone compatibility checker for MoClo assembly.

This module provides functions to check if cassettes are compatible
with backbones based on overhang matching.
"""

from typing import List, Dict, Any, Optional, Tuple
from app.models.cassette import Cassette
from app.models.backbone import Backbone
from app.services.restriction_sites import identify_cassette_slots


def check_compatibility(
    cassette: Cassette,
    backbone: Backbone,
    slot: Optional[int] = None,
    check_reverse: bool = True
) -> Dict[str, Any]:
    """
    Check if a cassette is compatible with a backbone.
    
    Compatibility is determined by matching overhangs:
    - Cassette 5' overhang must match backbone insertion site 5' overhang
    - Cassette 3' overhang must match backbone insertion site 3' overhang
    
    Also checks reverse complement orientation if check_reverse=True.
    
    Args:
        cassette: Cassette to check
        backbone: Backbone to check against
        slot: Specific slot number to check (None = check all slots)
        check_reverse: Whether to also check reverse complement orientation
        
    Returns:
        Dictionary with:
            - compatible: Boolean indicating compatibility
            - reason: Explanation of compatibility/incompatibility
            - matching_slots: List of compatible slot numbers
            - score: Compatibility score (0-100)
            - details: Detailed overhang comparison
            - orientation: 'forward' or 'reverse' (if compatible)
    """
    # Get cassette overhangs from the assembled sequence
    # In MoClo, overhangs are 4 bases at each end
    cassette_seq = cassette.assembled_sequence
    if len(cassette_seq) < 8:
        return {
            'compatible': False,
            'reason': 'Cassette sequence too short (must be at least 8 bases)',
            'matching_slots': [],
            'score': 0,
            'details': {},
            'orientation': None
        }
    
    cassette_5prime = cassette_seq[:4].upper()
    cassette_3prime = cassette_seq[-4:].upper()
    
    # Also get reverse complement overhangs
    if check_reverse:
        from app.services.restriction_sites import reverse_complement
        cassette_seq_rc = reverse_complement(cassette_seq)
        cassette_5prime_rc = cassette_seq_rc[:4].upper()
        cassette_3prime_rc = cassette_seq_rc[-4:].upper()
    
    # Get backbone restriction sites and slots
    sites = backbone.restriction_sites
    if not sites:
        return {
            'compatible': False,
            'reason': 'Backbone has no restriction sites detected',
            'matching_slots': [],
            'score': 0,
            'details': {},
            'orientation': None
        }
    
    # Check if sites are already in slot format (have slot_number key)
    # or if they need to be processed from raw restriction site data
    if sites and 'slot_number' in sites[0]:
        # Sites are already in slot format
        slots = sites
    else:
        # Sites need to be processed to identify slots
        slots = identify_cassette_slots(sites)
        
    if not slots:
        return {
            'compatible': False,
            'reason': 'Backbone has no valid cassette insertion slots',
            'matching_slots': [],
            'score': 0,
            'details': {},
            'orientation': None
        }
    
    # Check specific slot or all slots
    if slot is not None:
        slots_to_check = [s for s in slots if s['slot_number'] == slot]
        if not slots_to_check:
            return {
                'compatible': False,
                'reason': f'Slot {slot} not found in backbone',
                'matching_slots': [],
                'score': 0,
                'details': {},
                'orientation': None
            }
    else:
        slots_to_check = slots
    
    # Check each slot in both orientations
    matching_slots = []
    details = {}
    best_orientation = None
    
    for slot_info in slots_to_check:
        slot_num = slot_info['slot_number']
        # Handle both formats: 'expected_overhang_5prime' (from identify_cassette_slots)
        # or 'overhang_5prime' (from pre-processed backbone data)
        expected_5prime = slot_info.get('expected_overhang_5prime') or slot_info.get('overhang_5prime', 'NNNN')
        expected_3prime = slot_info.get('expected_overhang_3prime') or slot_info.get('overhang_3prime', 'NNNN')
        
        # Check forward orientation
        match_5prime_fwd = _overhangs_match(cassette_5prime, expected_5prime)
        match_3prime_fwd = _overhangs_match(cassette_3prime, expected_3prime)
        compatible_fwd = match_5prime_fwd and match_3prime_fwd
        
        # Check reverse orientation
        compatible_rc = False
        if check_reverse:
            match_5prime_rc = _overhangs_match(cassette_5prime_rc, expected_5prime)
            match_3prime_rc = _overhangs_match(cassette_3prime_rc, expected_3prime)
            compatible_rc = match_5prime_rc and match_3prime_rc
        
        details[f'slot_{slot_num}'] = {
            'expected_5prime': expected_5prime,
            'expected_3prime': expected_3prime,
            'forward': {
                'cassette_5prime': cassette_5prime,
                'cassette_3prime': cassette_3prime,
                'match_5prime': match_5prime_fwd,
                'match_3prime': match_3prime_fwd,
                'compatible': compatible_fwd
            }
        }
        
        if check_reverse:
            details[f'slot_{slot_num}']['reverse'] = {
                'cassette_5prime': cassette_5prime_rc,
                'cassette_3prime': cassette_3prime_rc,
                'match_5prime': match_5prime_rc,
                'match_3prime': match_3prime_rc,
                'compatible': compatible_rc
            }
        
        if compatible_fwd:
            matching_slots.append(slot_num)
            if best_orientation is None:
                best_orientation = 'forward'
        elif compatible_rc:
            matching_slots.append(slot_num)
            if best_orientation is None:
                best_orientation = 'reverse'
    
    # Determine overall compatibility
    compatible = len(matching_slots) > 0
    
    if compatible:
        if len(matching_slots) == 1:
            reason = f"Compatible with slot {matching_slots[0]} ({best_orientation} orientation)"
        else:
            reason = f"Compatible with slots {', '.join(map(str, matching_slots))} ({best_orientation} orientation)"
        score = 100
    else:
        # Provide specific reason for incompatibility
        if not details:
            reason = "No slots available for checking"
            score = 0
        else:
            # Find the closest match
            first_slot = list(details.values())[0]
            fwd = first_slot['forward']
            if not fwd['match_5prime'] and not fwd['match_3prime']:
                if check_reverse:
                    reason = f"Overhangs mismatch in both orientations (expected {first_slot['expected_5prime']}/{first_slot['expected_3prime']})"
                else:
                    reason = f"Both overhangs mismatch (expected {first_slot['expected_5prime']}/{first_slot['expected_3prime']}, got {cassette_5prime}/{cassette_3prime})"
                score = 0
            elif not fwd['match_5prime']:
                reason = f"5' overhang mismatch (expected {first_slot['expected_5prime']}, got {cassette_5prime})"
                score = 50
            else:
                reason = f"3' overhang mismatch (expected {first_slot['expected_3prime']}, got {cassette_3prime})"
                score = 50
    
    return {
        'compatible': compatible,
        'reason': reason,
        'matching_slots': matching_slots,
        'score': score,
        'details': details,
        'orientation': best_orientation
    }


def find_compatible_backbones(
    cassette: Cassette,
    backbones: Optional[List[Backbone]] = None
) -> List[Dict[str, Any]]:
    """
    Find all backbones compatible with a cassette.
    
    Args:
        cassette: Cassette to find backbones for
        backbones: List of backbones to check (None = check all)
        
    Returns:
        List of dictionaries with:
            - backbone: Backbone object
            - compatibility: Compatibility check result
    """
    if backbones is None:
        backbones = Backbone.get_all()
    
    compatible_backbones = []
    
    for backbone in backbones:
        compatibility = check_compatibility(cassette, backbone)
        
        if compatibility['compatible']:
            compatible_backbones.append({
                'backbone': backbone,
                'compatibility': compatibility
            })
    
    # Sort by compatibility score
    compatible_backbones.sort(
        key=lambda x: x['compatibility']['score'],
        reverse=True
    )
    
    return compatible_backbones


def find_compatible_cassettes(
    backbone: Backbone,
    cassettes: Optional[List[Cassette]] = None,
    slot: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Find all cassettes compatible with a backbone.
    
    Args:
        backbone: Backbone to find cassettes for
        cassettes: List of cassettes to check (None = check all)
        slot: Specific slot to check (None = any slot)
        
    Returns:
        List of dictionaries with:
            - cassette: Cassette object
            - compatibility: Compatibility check result
    """
    if cassettes is None:
        cassettes = Cassette.get_all()
    
    compatible_cassettes = []
    
    for cassette in cassettes:
        compatibility = check_compatibility(cassette, backbone, slot)
        
        if compatibility['compatible']:
            compatible_cassettes.append({
                'cassette': cassette,
                'compatibility': compatibility
            })
    
    # Sort by compatibility score and slot number
    compatible_cassettes.sort(
        key=lambda x: (
            x['compatibility']['score'],
            min(x['compatibility']['matching_slots']) if x['compatibility']['matching_slots'] else 999
        ),
        reverse=True
    )
    
    return compatible_cassettes


def get_compatibility_score(cassette: Cassette, backbone: Backbone) -> int:
    """
    Get a simple compatibility score (0-100) for a cassette-backbone pair.
    
    Args:
        cassette: Cassette to check
        backbone: Backbone to check
        
    Returns:
        Compatibility score (0 = incompatible, 100 = perfect match)
    """
    compatibility = check_compatibility(cassette, backbone)
    return compatibility['score']


def _overhangs_match(overhang1: str, overhang2: str) -> bool:
    """
    Check if two overhangs match.
    
    Handles ambiguous bases (N matches anything).
    
    Args:
        overhang1: First overhang sequence
        overhang2: Second overhang sequence
        
    Returns:
        True if overhangs match
    """
    # Handle None values
    if overhang1 is None or overhang2 is None:
        return False
    
    if len(overhang1) != len(overhang2):
        return False
    
    overhang1 = overhang1.upper()
    overhang2 = overhang2.upper()
    
    for base1, base2 in zip(overhang1, overhang2):
        # N matches anything
        if base1 == 'N' or base2 == 'N':
            continue
        
        # Exact match required
        if base1 != base2:
            return False
    
    return True


def get_insertion_position(
    cassette: Cassette,
    backbone: Backbone,
    slot: int = 1
) -> Optional[int]:
    """
    Determine where a cassette would be inserted in a backbone.
    
    Args:
        cassette: Cassette to insert
        backbone: Backbone to insert into
        slot: Slot number for insertion
        
    Returns:
        Insertion position (0-indexed) or None if incompatible
    """
    compatibility = check_compatibility(cassette, backbone, slot)
    
    if not compatibility['compatible']:
        return None
    
    # Get slot information
    sites = backbone.restriction_sites
    slots = identify_cassette_slots(sites)
    
    for slot_info in slots:
        if slot_info['slot_number'] == slot:
            return slot_info['insertion_start']
    
    return None


def explain_incompatibility(cassette: Cassette, backbone: Backbone) -> str:
    """
    Get a detailed explanation of why a cassette is incompatible with a backbone.
    
    Args:
        cassette: Cassette to check
        backbone: Backbone to check
        
    Returns:
        Human-readable explanation string
    """
    compatibility = check_compatibility(cassette, backbone)
    
    if compatibility['compatible']:
        return f"Cassette is compatible with {backbone.name}"
    
    explanation = [f"Cassette '{cassette.name}' is incompatible with backbone '{backbone.name}':"]
    explanation.append(f"  Reason: {compatibility['reason']}")
    
    # Add details for each slot
    for slot_key, slot_details in compatibility['details'].items():
        slot_num = slot_key.split('_')[1]
        explanation.append(f"\n  Slot {slot_num}:")
        explanation.append(f"    Expected overhangs: {slot_details['expected_5prime']} / {slot_details['expected_3prime']}")
        explanation.append(f"    Cassette overhangs: {slot_details['cassette_5prime']} / {slot_details['cassette_3prime']}")
        
        if not slot_details['match_5prime']:
            explanation.append(f"    ✗ 5' overhang mismatch")
        else:
            explanation.append(f"    ✓ 5' overhang matches")
        
        if not slot_details['match_3prime']:
            explanation.append(f"    ✗ 3' overhang mismatch")
        else:
            explanation.append(f"    ✓ 3' overhang matches")
    
    return '\n'.join(explanation)


def batch_check_compatibility(
    cassettes: List[Cassette],
    backbones: List[Backbone]
) -> Dict[str, Dict[str, bool]]:
    """
    Check compatibility for multiple cassette-backbone pairs.
    
    Args:
        cassettes: List of cassettes
        backbones: List of backbones
        
    Returns:
        Dictionary mapping cassette IDs to backbone ID compatibility:
        {
            'cassette_id_1': {
                'backbone_id_1': True,
                'backbone_id_2': False,
                ...
            },
            ...
        }
    """
    results = {}
    
    for cassette in cassettes:
        results[cassette.id] = {}
        
        for backbone in backbones:
            compatibility = check_compatibility(cassette, backbone)
            results[cassette.id][backbone.id] = compatibility['compatible']
    
    return results
