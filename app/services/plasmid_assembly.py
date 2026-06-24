"""
Plasmid assembly engine for MoClo Golden Gate assembly.

This module provides functions to assemble cassettes into backbones
to create final plasmids, including sequence assembly and feature merging.
"""

from typing import List, Dict, Any, Optional, Tuple
from app.models.cassette import Cassette
from app.models.backbone import Backbone
from app.models.final_plasmid import FinalPlasmid
from app.models.part import Part
from app.services.backbone_compatibility import check_compatibility
from app.services.restriction_sites import identify_cassette_slots
import re


class AssemblyError(Exception):
    """Exception raised when assembly fails."""
    pass


def assemble_plasmid(
    backbone: Backbone,
    cassettes: List[Cassette],
    slots: Optional[List[int]] = None,
    orientations: Optional[List[str]] = None,
    name: Optional[str] = None,
    owner_id: Optional[str] = None
) -> FinalPlasmid:
    """
    Assemble one or more cassettes into a backbone to create a final plasmid.
    
    This performs Golden Gate assembly:
    1. Digest backbone at restriction sites
    2. Remove restriction sites from cassette sequences
    3. Insert cassettes at appropriate positions (forward or reverse complement)
    4. Ligate to form circular plasmid
    5. Merge features from backbone and cassettes
    
    Args:
        backbone: Backbone to insert into
        cassettes: List of cassettes to insert (in order)
        slots: List of slot numbers for each cassette (None = auto-assign)
        orientations: List of orientations for each cassette ('forward' or 'reverse', None = auto-detect)
        name: Name for the final plasmid (None = auto-generate)
        owner_id: Owner of the plasmid (None = use backbone owner)
        
    Returns:
        FinalPlasmid instance
        
    Raises:
        AssemblyError: If assembly fails due to incompatibility or other issues
    """
    # Validate inputs
    if not cassettes:
        raise AssemblyError("At least one cassette is required for assembly")
    
    # Auto-assign slots if not provided
    if slots is None:
        slots = list(range(1, len(cassettes) + 1))
    
    if len(slots) != len(cassettes):
        raise AssemblyError(f"Number of slots ({len(slots)}) must match number of cassettes ({len(cassettes)})")
    
    # Auto-detect orientations if not provided
    if orientations is None:
        orientations = []
        for cassette, slot in zip(cassettes, slots):
            compatibility = check_compatibility(cassette, backbone, slot)
            if not compatibility['compatible']:
                raise AssemblyError(
                    f"Cassette '{cassette.name}' is not compatible with backbone '{backbone.name}' "
                    f"at slot {slot}: {compatibility['reason']}"
                )
            orientations.append(compatibility['orientation'])
    else:
        if len(orientations) != len(cassettes):
            raise AssemblyError(f"Number of orientations ({len(orientations)}) must match number of cassettes ({len(cassettes)})")
        
        # Validate orientations
        for orientation in orientations:
            if orientation not in ['forward', 'reverse']:
                raise AssemblyError(f"Invalid orientation: {orientation}. Must be 'forward' or 'reverse'")
    
    # Check compatibility for each cassette with specified orientation
    for i, (cassette, slot, orientation) in enumerate(zip(cassettes, slots, orientations)):
        compatibility = check_compatibility(cassette, backbone, slot)
        if not compatibility['compatible']:
            raise AssemblyError(
                f"Cassette '{cassette.name}' is not compatible with backbone '{backbone.name}' "
                f"at slot {slot}: {compatibility['reason']}"
            )
        
        # Verify the specified orientation is compatible
        if orientation not in [compatibility['orientation'], None]:
            # Check if the specified orientation is actually compatible
            slot_details = compatibility['details'].get(f'slot_{slot}', {})
            orientation_details = slot_details.get(orientation, {})
            if not orientation_details.get('compatible', False):
                raise AssemblyError(
                    f"Cassette '{cassette.name}' is not compatible in {orientation} orientation at slot {slot}"
                )
    
    # Get backbone slots information
    # Check if restriction_sites are already in slot format or need processing
    if backbone.restriction_sites and 'slot_number' in backbone.restriction_sites[0]:
        # Already in slot format
        backbone_slots = backbone.restriction_sites
    else:
        # Need to process raw restriction site data
        backbone_slots = identify_cassette_slots(backbone.restriction_sites)
    
    if not backbone_slots:
        raise AssemblyError(f"Backbone '{backbone.name}' has no valid insertion slots")
    
    # Perform assembly with orientations
    assembled_sequence = _assemble_sequence(backbone, cassettes, slots, backbone_slots, orientations)
    
    # Merge features
    merged_features = _merge_features(backbone, cassettes, slots, backbone_slots, orientations)
    
    # Generate name if not provided
    if name is None:
        cassette_names = '_'.join(c.name[:10] for c in cassettes)
        name = f"{backbone.name}_{cassette_names}"
    
    # Use backbone owner if not specified
    if owner_id is None:
        owner_id = backbone.owner_id
    
    # Create metadata with cassette positions and orientations
    cassette_positions = []
    for cassette, slot, orientation in zip(cassettes, slots, orientations):
        slot_info = next((s for s in backbone_slots if s['slot_number'] == slot), None)
        if slot_info:
            # Handle both slot formats
            if 'insertion_start' in slot_info:
                # Detailed format with position information
                cassette_start = slot_info['insertion_start']
                cassette_length = len(cassette.assembled_sequence) - 8  # Minus overhangs
                cassette_end = cassette_start + cassette_length
            else:
                # Simplified format - use approximate position
                cassette_start = len(backbone.sequence) // 2
                cassette_length = len(cassette.assembled_sequence) - 8
                cassette_end = cassette_start + cassette_length
            
            cassette_positions.append({
                'cassette_name': cassette.name,
                'slot': slot,
                'start': cassette_start,
                'end': cassette_end,
                'orientation': orientation
            })
    
    metadata = {
        'backbone_name': backbone.name,
        'cassette_names': [c.name for c in cassettes],
        'assembly_method': 'MoClo Golden Gate',
        'slots_used': slots,
        'orientations': orientations,
        'cassette_positions': cassette_positions,
        'moclo_level': moclo_level
    }
    
    # Include per-cassette part details (type, translation, introns)
    cassette_details = []
    for cassette in cassettes:
        detail = {
            'cassette_id': cassette.id,
            'cassette_name': cassette.name,
            'cassette_level': cassette.level,
        }
        if cassette.parts_metadata:
            detail['parts'] = cassette.parts_metadata
        if cassette.translation_data:
            detail['translation'] = cassette.translation_data
        cassette_details.append(detail)
    metadata['cassette_details'] = cassette_details
    
    # Analyze translation for the assembled plasmid (level-aware)
    from app.services.translation import analyze_plasmid_translation
    translation_result = analyze_plasmid_translation(
        plasmid_sequence=assembled_sequence,
        cassettes=cassettes,
        plasmid_level=moclo_level
    )
    metadata['translation'] = translation_result
    
    # Create final plasmid
    plasmid = FinalPlasmid.create(
        name=name,
        owner_id=owner_id,
        backbone_id=backbone.id,
        cassette_ids=[c.id for c in cassettes],
        assembled_sequence=assembled_sequence,
        features=merged_features,
        metadata=metadata
    )
    
    # Automatically create a part from this plasmid for hierarchical assembly
    # Determine the MoClo level based on the backbone's restriction enzyme
    moclo_level = _determine_moclo_level(backbone)
    
    # Create part from the assembled plasmid
    try:
        from app.models.part import Part
        from app.services.restriction_sites import find_moclo_sites
        
        # Find restriction sites in the assembled plasmid to determine overhangs
        # For Level 1: look for BpiI sites (for Level 2 assembly)
        # For Level 2: look for BsaI sites (for Level 3 assembly, if applicable)
        next_enzyme = 'BpiI' if moclo_level == 1 else 'BsaI'
        sites = find_moclo_sites(assembled_sequence, enzyme=next_enzyme)
        
        if len(sites) >= 2:
            # Extract overhangs from the first and last sites
            # The plasmid can be used as a part in the next level
            overhang_5prime = sites[0]['overhang_5prime']
            overhang_3prime = sites[-1]['overhang_3prime']
            
            # Determine part type based on level
            # Level 1 plasmids become "Coding" parts (transcription units)
            # Level 2+ become "NonCodingOther" (multi-gene constructs)
            part_type = 'Coding' if moclo_level == 1 else 'NonCodingOther'
            
            # Create part name with level designation
            part_name = f"{name}_L{moclo_level}"
            
            # Create the part
            new_part = Part.create(
                name=part_name,
                part_type=part_type,
                sequence=assembled_sequence,
                overhang_5prime=overhang_5prime,
                overhang_3prime=overhang_3prime,
                contributor=owner_id,
                lab_source=f"Assembled from plasmid {name}",
                level=str(moclo_level),
                comments=f"MoClo Level {moclo_level} construct. Auto-generated from plasmid assembly."
            )
            
            # Store reference to the part in plasmid metadata
            plasmid.metadata['created_part_id'] = new_part.id
            plasmid.metadata['moclo_level'] = moclo_level
            plasmid.update()
            
    except Exception as e:
        # Don't fail the plasmid creation if part creation fails
        # Just log the error
        import logging
        logging.warning(f"Failed to create part from plasmid: {str(e)}")
    
    return plasmid


def _assemble_sequence(
    backbone: Backbone,
    cassettes: List[Cassette],
    slots: List[int],
    backbone_slots: List[Dict[str, Any]],
    orientations: List[str]
) -> str:
    """
    Assemble the final plasmid sequence.
    
    Args:
        backbone: Backbone sequence
        cassettes: List of cassettes to insert
        slots: Slot numbers for each cassette
        backbone_slots: Slot information from backbone
        orientations: List of orientations for each cassette ('forward' or 'reverse')
        
    Returns:
        Assembled circular plasmid sequence
    """
    from app.services.restriction_sites import reverse_complement
    
    # Start with backbone sequence
    sequence = backbone.sequence
    
    # For simplified slot format (without insertion positions), 
    # we'll do a simple concatenation approach
    if backbone_slots and 'insertion_start' not in backbone_slots[0]:
        # Simplified assembly: just concatenate cassette sequences (minus overhangs)
        # This works for single-slot backbones
        cassette_inserts = []
        for cassette, orientation in zip(cassettes, orientations):
            cassette_seq = cassette.assembled_sequence
            
            # Reverse complement if needed
            if orientation == 'reverse':
                cassette_seq = reverse_complement(cassette_seq)
            
            # Remove overhangs (first 4 and last 4 bases)
            if len(cassette_seq) > 8:
                cassette_inserts.append(cassette_seq[4:-4])
            else:
                cassette_inserts.append(cassette_seq)
        
        # For single-slot backbones, insert at the middle
        # This is a simplified approach - in reality, we'd need the actual restriction site positions
        insert_pos = len(sequence) // 2
        assembled = sequence[:insert_pos] + ''.join(cassette_inserts) + sequence[insert_pos:]
        return assembled
    
    # Sort cassettes by slot position (reverse order for proper insertion)
    cassette_slot_orientation_tuples = sorted(
        zip(cassettes, slots, orientations),
        key=lambda x: x[1],
        reverse=True
    )
    
    # Insert each cassette at its slot
    for cassette, slot_num, orientation in cassette_slot_orientation_tuples:
        # Find the slot information
        slot_info = next((s for s in backbone_slots if s['slot_number'] == slot_num), None)
        if not slot_info:
            raise AssemblyError(f"Slot {slot_num} not found in backbone")
        
        # Insert cassette at this position
        sequence = _insert_cassette_at_slot(sequence, cassette, slot_info, orientation)
    
    return sequence


def _insert_cassette_at_slot(
    backbone_seq: str,
    cassette: Cassette,
    slot_info: Dict[str, Any],
    orientation: str = 'forward'
) -> str:
    """
    Insert a cassette sequence at a specific slot in the backbone.
    
    In Golden Gate assembly:
    1. The restriction sites are removed during digestion
    2. The cassette sequence (without its overhangs) is inserted
    3. The overhangs ligate to the backbone overhangs
    4. Cassette can be inserted in forward or reverse complement orientation
    
    Args:
        backbone_seq: Current backbone sequence
        cassette: Cassette to insert
        slot_info: Slot information dictionary
        orientation: 'forward' or 'reverse' orientation
        
    Returns:
        Modified sequence with cassette inserted
    """
    from app.services.restriction_sites import reverse_complement
    
    insertion_start = slot_info['insertion_start']
    insertion_end = slot_info['insertion_end']
    
    # Get cassette sequence
    cassette_seq = cassette.assembled_sequence
    
    # Reverse complement if needed
    if orientation == 'reverse':
        cassette_seq = reverse_complement(cassette_seq)
    
    # In MoClo, the overhangs are the first 4 and last 4 bases
    # These will be removed during Golden Gate assembly
    if len(cassette_seq) > 8:
        cassette_insert = cassette_seq[4:-4]
    else:
        cassette_insert = cassette_seq
    
    # Build new sequence:
    # [backbone before slot] + [cassette without overhangs] + [backbone after slot]
    new_sequence = (
        backbone_seq[:insertion_start] +
        cassette_insert +
        backbone_seq[insertion_end:]
    )
    
    return new_sequence


def _merge_features(
    backbone: Backbone,
    cassettes: List[Cassette],
    slots: List[int],
    backbone_slots: List[Dict[str, Any]],
    orientations: List[str]
) -> List[Dict[str, Any]]:
    """
    Merge features from backbone and cassettes.
    
    Features from cassettes are inserted at their respective positions,
    and all feature positions are adjusted accordingly.
    
    Args:
        backbone: Backbone with features
        cassettes: List of cassettes with features
        slots: Slot numbers for each cassette
        backbone_slots: Slot information
        orientations: List of orientations for each cassette ('forward' or 'reverse')
        
    Returns:
        List of merged feature dictionaries
    """
    merged_features = []
    
    # Start with backbone features
    backbone_features = backbone.features.copy() if backbone.features else []
    
    # Handle simplified slot format (no position information)
    if backbone_slots and 'insertion_start' not in backbone_slots[0]:
        # For simplified format, just add features without position adjustments
        merged_features.extend(backbone_features)
        
        # Add cassette features at approximate positions
        for cassette, slot_num, orientation in zip(cassettes, slots, orientations):
            # Use approximate position (middle of backbone)
            insertion_pos = len(backbone.sequence) // 2
            cassette_features = _get_cassette_features(cassette, insertion_pos, orientation)
            merged_features.extend(cassette_features)
        
        return merged_features
    
    # Calculate position adjustments for each insertion
    position_adjustments = _calculate_position_adjustments(
        backbone, cassettes, slots, backbone_slots
    )
    
    # Adjust backbone features
    for feature in backbone_features:
        adjusted_feature = _adjust_feature_position(feature, position_adjustments)
        if adjusted_feature:
            merged_features.append(adjusted_feature)
    
    # Add cassette features
    for cassette, slot_num, orientation in zip(cassettes, slots, orientations):
        slot_info = next((s for s in backbone_slots if s['slot_number'] == slot_num), None)
        if not slot_info:
            continue
        
        insertion_pos = slot_info['insertion_start']
        
        # Get parts for this cassette
        cassette_features = _get_cassette_features(cassette, insertion_pos, orientation)
        merged_features.extend(cassette_features)
    
    # Sort features by position
    merged_features.sort(key=lambda f: f['start'])
    
    return merged_features


def _calculate_position_adjustments(
    backbone: Backbone,
    cassettes: List[Cassette],
    slots: List[int],
    backbone_slots: List[Dict[str, Any]]
) -> List[Tuple[int, int]]:
    """
    Calculate how much to adjust positions after each insertion.
    
    Returns list of (position, adjustment) tuples.
    """
    adjustments = []
    cumulative_adjustment = 0
    
    # Sort by slot position
    cassette_slot_pairs = sorted(zip(cassettes, slots), key=lambda x: x[1])
    
    for cassette, slot_num in cassette_slot_pairs:
        slot_info = next((s for s in backbone_slots if s['slot_number'] == slot_num), None)
        if not slot_info:
            continue
        
        insertion_pos = slot_info['insertion_start']
        removed_length = slot_info['insertion_length']
        
        # Cassette length without overhangs (4 bases on each end)
        cassette_length = len(cassette.assembled_sequence) - 8
        
        # Net change in length
        length_change = cassette_length - removed_length
        
        adjustments.append((insertion_pos + cumulative_adjustment, length_change))
        cumulative_adjustment += length_change
    
    return adjustments


def _adjust_feature_position(
    feature: Dict[str, Any],
    adjustments: List[Tuple[int, int]]
) -> Optional[Dict[str, Any]]:
    """
    Adjust a feature's position based on insertions.
    
    Args:
        feature: Feature dictionary
        adjustments: List of (position, adjustment) tuples
        
    Returns:
        Adjusted feature or None if feature was removed
    """
    adjusted_feature = feature.copy()
    start = feature['start']
    end = feature['end']
    
    # Apply adjustments
    for adj_pos, adj_amount in adjustments:
        if start >= adj_pos:
            start += adj_amount
        if end >= adj_pos:
            end += adj_amount
    
    adjusted_feature['start'] = start
    adjusted_feature['end'] = end
    
    return adjusted_feature


def _get_cassette_features(cassette: Cassette, insertion_pos: int, orientation: str = 'forward') -> List[Dict[str, Any]]:
    """
    Get features from a cassette, adjusted for insertion position and orientation.
    
    Args:
        cassette: Cassette to get features from
        insertion_pos: Position where cassette is inserted
        orientation: 'forward' or 'reverse' orientation
        
    Returns:
        List of feature dictionaries including overlap annotations
    """
    features = []
    
    # Get parts for this cassette
    parts = []
    for part_id in cassette.part_ids:
        part = Part.get_by_id(part_id)
        if part:
            parts.append(part)
    
    # If reverse orientation, reverse the order of parts
    if orientation == 'reverse':
        parts = list(reversed(parts))
    
    # Calculate positions for each part in the cassette
    current_pos = insertion_pos
    
    for i, part in enumerate(parts):
        # Determine strand based on orientation
        strand = 1 if orientation == 'forward' else -1
        
        # Calculate part length in assembled cassette
        if i == 0:
            # First part: full length
            part_start = current_pos
            part_length = len(part.sequence)
            part_end = part_start + part_length
        else:
            # Subsequent parts: overlap with previous part
            # The 4bp overhang is shared between parts
            overlap_start = current_pos
            overlap_end = current_pos + 4
            
            # Add overlap feature
            features.append({
                'type': 'misc_feature',
                'start': overlap_start,
                'end': overlap_end,
                'strand': strand,
                'label': f'Overlap: {parts[i-1].name}/{part.name}',
                'qualifiers': {
                    'note': f'4bp overlap between {parts[i-1].name} and {part.name}',
                    'overlap': 'true',
                    'overhang': part.overhang_5prime if orientation == 'forward' else part.overhang_3prime,
                    'orientation': orientation
                }
            })
            
            # Part starts at overlap position
            part_start = current_pos
            part_length = len(part.sequence)
            part_end = part_start + part_length
        
        # Create feature for this part
        feature = {
            'type': _part_type_to_feature_type(part.part_type),
            'start': part_start,
            'end': part_end,
            'strand': strand,
            'label': part.name + (' (RC)' if orientation == 'reverse' else ''),
            'qualifiers': {
                'part_type': part.part_type,
                'source': 'cassette',
                'lab_source': part.lab_source if hasattr(part, 'lab_source') else None,
                'contributor': part.contributor if hasattr(part, 'contributor') else None,
                'overhang_5prime': part.overhang_5prime,
                'overhang_3prime': part.overhang_3prime,
                'orientation': orientation
            }
        }
        
        features.append(feature)
        
        # Move position forward by part length minus overlap (except for first part)
        if i == 0:
            current_pos += part_length - 4  # Remove 3' overhang
        else:
            current_pos += part_length - 4  # Remove 3' overhang (5' was already overlapped)
    
    return features


def _part_type_to_feature_type(part_type: str) -> str:
    """
    Convert part type to GenBank feature type.
    
    Args:
        part_type: Part type (Coding, NonCodingPromoter, etc.)
        
    Returns:
        GenBank feature type
    """
    type_map = {
        'Coding': 'CDS',
        'NonCodingPromoter': 'promoter',
        'NonCodingTerminator': 'terminator',
        'NonCodingIntron': 'intron',
        'NonCodingOther': 'misc_feature'
    }
    
    return type_map.get(part_type, 'misc_feature')


def _determine_moclo_level(backbone: Backbone) -> int:
    """
    Determine the MoClo level based on the backbone's restriction enzyme
    and/or the backbone's level metadata.
    
    In MoClo hierarchy:
    - Level 0 parts use BsaI → assembled into Level 1 cassettes
    - Level 1 cassettes use BpiI → assembled into Level 2 plasmids
    - Level 2 cassettes use BsaI → assembled into Level 3 (if needed)
    
    Args:
        backbone: Backbone used for assembly
        
    Returns:
        MoClo level (1, 2, or 3)
    """
    # First check the backbone's explicit level metadata
    if hasattr(backbone, 'level') and backbone.level:
        try:
            bb_level = int(backbone.level)
            # The assembled plasmid is at the backbone's level
            # (a Level 1 backbone produces Level 1 plasmids from Level 0 parts,
            #  a Level 2 backbone produces Level 2 plasmids from Level 1 cassettes)
            if bb_level in (1, 2, 3):
                return bb_level
        except (ValueError, TypeError):
            pass
    
    if not backbone.restriction_sites:
        return 1  # Default to Level 1
    
    # Check which enzyme is used in the backbone
    enzymes = set(site.get('enzyme', 'BsaI') for site in backbone.restriction_sites)
    
    if 'BsaI' in enzymes:
        # BsaI backbone = Level 0 → Level 1 assembly
        return 1
    elif 'BpiI' in enzymes:
        # BpiI backbone = Level 1 → Level 2 assembly
        return 2
    else:
        # Default or other enzymes
        return 1


def remove_restriction_sites(
    sequence: str,
    enzyme: str = 'BsaI'
) -> str:
    """
    Remove restriction sites from a sequence (simulates Golden Gate assembly).
    
    In Golden Gate assembly, the restriction sites are destroyed after ligation.
    
    Args:
        sequence: DNA sequence
        enzyme: Restriction enzyme used
        
    Returns:
        Sequence with restriction sites removed
    """
    from app.services.restriction_sites import MOCLO_ENZYMES
    
    if enzyme not in MOCLO_ENZYMES:
        return sequence
    
    recognition = MOCLO_ENZYMES[enzyme]['recognition']
    
    # Remove all occurrences of the recognition site
    # In reality, they're destroyed during ligation, not just removed
    cleaned_sequence = sequence.replace(recognition, '')
    
    return cleaned_sequence


def validate_assembly(
    backbone: Backbone,
    cassettes: List[Cassette],
    slots: Optional[List[int]] = None
) -> Tuple[bool, str]:
    """
    Validate that an assembly is possible before attempting it.
    
    Args:
        backbone: Backbone to use
        cassettes: Cassettes to insert
        slots: Slot assignments
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check basic requirements
    if not cassettes:
        return False, "At least one cassette is required"
    
    if not backbone.restriction_sites:
        return False, f"Backbone '{backbone.name}' has no restriction sites"
    
    # Check if restriction_sites are already in slot format or need processing
    if 'slot_number' in backbone.restriction_sites[0]:
        # Already in slot format
        backbone_slots = backbone.restriction_sites
    else:
        # Need to process raw restriction site data
        backbone_slots = identify_cassette_slots(backbone.restriction_sites)
    
    if not backbone_slots:
        return False, f"Backbone '{backbone.name}' has no valid insertion slots"
    
    # Auto-assign slots if needed
    if slots is None:
        slots = list(range(1, len(cassettes) + 1))
    
    if len(slots) != len(cassettes):
        return False, f"Number of slots ({len(slots)}) must match number of cassettes ({len(cassettes)})"
    
    # Check if all slots exist
    available_slots = [s['slot_number'] for s in backbone_slots]
    for slot in slots:
        if slot not in available_slots:
            return False, f"Slot {slot} does not exist in backbone (available: {available_slots})"
    
    # Check compatibility for each cassette
    for cassette, slot in zip(cassettes, slots):
        compatibility = check_compatibility(cassette, backbone, slot)
        if not compatibility['compatible']:
            return False, f"Cassette '{cassette.name}' incompatible with slot {slot}: {compatibility['reason']}"
    
    return True, "Assembly is valid"


def simulate_assembly(
    backbone: Backbone,
    cassettes: List[Cassette],
    slots: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Simulate an assembly without creating the plasmid.
    
    Useful for previewing the result before committing.
    
    Args:
        backbone: Backbone to use
        cassettes: Cassettes to insert
        slots: Slot assignments
        
    Returns:
        Dictionary with simulation results:
            - success: Whether assembly is valid
            - message: Status message
            - expected_length: Expected plasmid size
            - feature_count: Number of features
            - cassette_positions: Where each cassette will be inserted
            - error: Error message if not successful
    """
    # Validate first
    is_valid, message = validate_assembly(backbone, cassettes, slots)
    
    if not is_valid:
        return {
            'success': False,
            'error': message,
            'expected_length': 0,
            'feature_count': 0,
            'cassette_positions': []
        }
    
    # Calculate expected size
    if slots is None:
        slots = list(range(1, len(cassettes) + 1))
    
    # Check if restriction_sites are already in slot format or need processing
    if 'slot_number' in backbone.restriction_sites[0]:
        # Already in slot format
        backbone_slots = backbone.restriction_sites
    else:
        # Need to process raw restriction site data
        backbone_slots = identify_cassette_slots(backbone.restriction_sites)
    
    final_size = len(backbone.sequence)
    cassette_positions = []
    
    # Handle simplified slot format
    if backbone_slots and 'insertion_start' not in backbone_slots[0]:
        # Simplified calculation
        for cassette, slot in zip(cassettes, slots):
            # Add cassette length (minus overhangs)
            final_size += len(cassette.assembled_sequence) - 8
            
            cassette_positions.append({
                'cassette': cassette.name,
                'slot': slot,
                'position': len(backbone.sequence) // 2  # Approximate position
            })
    else:
        # Detailed calculation with insertion positions
        for cassette, slot in zip(cassettes, slots):
            slot_info = next((s for s in backbone_slots if s['slot_number'] == slot), None)
            if slot_info:
                # Remove the insertion region
                final_size -= slot_info['insertion_length']
                # Add cassette (minus overhangs)
                final_size += len(cassette.assembled_sequence) - 8
                
                cassette_positions.append({
                    'cassette': cassette.name,
                    'slot': slot,
                    'position': slot_info['insertion_start']
                })
    
    # Count features
    feature_count = len(backbone.features) if backbone.features else 0
    for cassette in cassettes:
        feature_count += len(cassette.part_ids)
    
    return {
        'success': True,
        'message': 'Assembly simulation successful',
        'expected_length': final_size,
        'feature_count': feature_count,
        'cassette_positions': cassette_positions
    }
