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
from app.services.restriction_sites import (
    identify_cassette_slots,
    compute_slot_overhangs,
    reverse_complement,
)
import re


class AssemblyError(Exception):
    """Exception raised when assembly fails."""
    pass


def backbone_slots(backbone) -> List[Dict[str, Any]]:
    """Resolve a backbone's cassette-insertion slots.

    Prefers a faithful Type IIS digest of ``backbone.sequence``
    (``compute_slot_overhangs``), which yields the exact excision window and the
    two fusion overhangs. Falls back to the older recognition-position heuristic
    only for backbones whose sequence has no clean convergent site pair (for
    example hand-built fixtures that carry pre-set ``restriction_sites``).
    """
    slots = compute_slot_overhangs(getattr(backbone, 'sequence', '') or '')
    if slots:
        return slots
    sites = getattr(backbone, 'restriction_sites', None) or []
    if sites and 'slot_number' in sites[0]:
        return sites
    return identify_cassette_slots(sites)


def _chain_cassettes(cassettes: List[Cassette]) -> Cassette:
    """Concatenate several Level 1 cassettes into one insert for a single-slot
    backbone, sharing the 4 bp overhang at each internal junction exactly once.

    Requires each cassette's 3' overhang to equal the next cassette's 5' overhang.
    Returns a lightweight in-memory Cassette (not persisted).
    """
    for a, b in zip(cassettes, cassettes[1:]):
        if a.assembled_sequence[-4:].upper() != b.assembled_sequence[:4].upper():
            raise AssemblyError(
                f"Cassettes '{a.name}' and '{b.name}' do not chain: 3' overhang "
                f"{a.assembled_sequence[-4:]} != 5' overhang {b.assembled_sequence[:4]}"
            )
    seq = cassettes[0].assembled_sequence
    for c in cassettes[1:]:
        seq += c.assembled_sequence[4:]
    part_ids = [pid for c in cassettes for pid in (c.part_ids or [])]
    return Cassette(
        id='+'.join(c.id for c in cassettes),
        name=' + '.join(c.name for c in cassettes),
        owner_id=cassettes[0].owner_id,
        part_ids=part_ids,
        assembled_sequence=seq,
        level=cassettes[0].level,
        parts_metadata=[m for c in cassettes for m in (c.parts_metadata or [])],
    )


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

    # A single-slot acceptor with several cassettes: chain them into one insert,
    # sharing each internal 4 bp overhang once (true one-pot MoClo multigene).
    available = backbone_slots(backbone)
    if (len(cassettes) > 1 and len(available) == 1
            and (slots is None or len(set(slots)) == 1)):
        cassettes = [_chain_cassettes(cassettes)]
        slots = [available[0]['slot_number']]
        if orientations is not None:
            orientations = ['forward']

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
    
    # Get backbone slots information (faithful Type IIS digest of the sequence)
    bb_slots = backbone_slots(backbone)
    if not bb_slots:
        raise AssemblyError(f"Backbone '{backbone.name}' has no valid insertion slots")

    # Perform assembly with orientations
    assembled_sequence = _assemble_sequence(backbone, cassettes, slots, bb_slots, orientations)

    # Merge features
    merged_features = _merge_features(backbone, cassettes, slots, bb_slots, orientations)
    
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
        slot_info = next((s for s in bb_slots if s['slot_number'] == slot), None)
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
    
    # Determine the MoClo level based on the backbone
    moclo_level = _determine_moclo_level(backbone)
    
    metadata = {
        'backbone_name': backbone.name,
        'backbone_id': backbone.id,
        'backbone_plasmid_id': backbone.plasmid_id if hasattr(backbone, 'plasmid_id') else None,
        'backbone_size': backbone.size,
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

    # Build an explicit MoClo assembly strategy: the flat fragment list that
    # the reaction-mix calculator consumes (backbone as the acceptor vector plus
    # one insert per component part). For a Level 2 plasmid the component parts
    # are the Level 1 units; where a unit carries a captured Level 0 breakdown
    # (sub_parts, e.g. the Guide Designer's promoter + tRNA-sgRNA modules) it is
    # expanded so the strategy shows the real Level 0 provenance.
    strat_enzyme = 'BpiI' if moclo_level == 2 else 'BsaI'
    strat_level_label = ('Level 1 \u2192 Level 2' if moclo_level == 2
                         else 'Level 0 \u2192 Level 1')
    strategy_fragments = [{
        'name': backbone.name,
        'size': backbone.size,
        'role': 'vector',
        'part_type': 'Backbone',
        'overhang_5prime': getattr(backbone, 'overhang_5prime', None),
        'overhang_3prime': getattr(backbone, 'overhang_3prime', None),
        'source_vector': backbone.plasmid_id if hasattr(backbone, 'plasmid_id') else None,
    }]
    for cassette in cassettes:
        for p in (cassette.parts_metadata or []):
            # Skip pure structural fillers from the insert list is NOT done here:
            # dummies/end-linkers are real plasmids the user pipettes, so they
            # belong in the reaction. Expand captured Level 0 sub-parts.
            sub = p.get('sub_parts')
            rows = sub if sub else [p]
            for r in rows:
                size = r.get('size') or r.get('sequence_length') or 0
                strategy_fragments.append({
                    'name': r.get('part_name', 'Part'),
                    'size': size,
                    'role': 'insert',
                    'part_type': r.get('part_type', ''),
                    'level': r.get('level'),
                    'overhang_5prime': r.get('overhang_5prime'),
                    'overhang_3prime': r.get('overhang_3prime'),
                    'source_vector': r.get('source_vector'),
                    'cassette_name': cassette.name,
                })
    metadata['moclo_strategy'] = {
        'enzyme': strat_enzyme,
        'moclo_level': moclo_level,
        'level_label': strat_level_label,
        'fragments': strategy_fragments,
    }

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
            
            # Build assembly lineage description
            part_components = []
            for cassette in cassettes:
                if cassette.parts_metadata:
                    cassette_parts = [p.get('part_name', 'Unknown') for p in cassette.parts_metadata]
                    part_components.append(f"{cassette.name} [{', '.join(cassette_parts)}]")
                else:
                    part_components.append(cassette.name)
            
            assembly_lineage = (
                f"MoClo Level {moclo_level} construct. "
                f"Backbone: {backbone.name}"
                f"{' (' + backbone.plasmid_id + ')' if hasattr(backbone, 'plasmid_id') and backbone.plasmid_id else ''}. "
                f"Cassettes: {'; '.join(part_components)}."
            )
            
            # Create the part with features list — only features between the enzyme sites
            # (the insert region, not backbone features like oriV, AmpR, etc.)
            insert_start = sites[0]['position']
            insert_end = sites[-1]['position']
            
            # Filter features to only those within the insert region
            insert_features = []
            for feat in merged_features:
                feat_start = feat.get('start', 0)
                feat_end = feat.get('end', 0)
                # Feature must be fully or mostly within the insert region
                if feat_start >= insert_start and feat_end <= insert_end:
                    insert_features.append(feat)
                elif feat_start < insert_end and feat_end > insert_start:
                    # Partially overlapping — include if majority is within insert
                    overlap = min(feat_end, insert_end) - max(feat_start, insert_start)
                    feat_length = feat_end - feat_start
                    if feat_length > 0 and overlap / feat_length > 0.5:
                        insert_features.append(feat)
            
            new_part = Part.create(
                name=part_name,
                part_type=part_type,
                sequence=assembled_sequence,
                overhang_5prime=overhang_5prime,
                overhang_3prime=overhang_3prime,
                contributor=owner_id,
                lab_source=f"Assembled from {backbone.name}",
                level=str(moclo_level),
                comments=assembly_lineage,
                features=insert_features,
                plasmid_id=plasmid.id
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
                'part_id': part.id,
                'part_type': part.part_type,
                'part_level': part.level or '0',
                'source': 'cassette',
                'source_vector': part.plasmid_id if hasattr(part, 'plasmid_id') and part.plasmid_id else None,
                'lab_source': part.lab_source if hasattr(part, 'lab_source') else None,
                'contributor': part.contributor if hasattr(part, 'contributor') else None,
                'overhang_5prime': part.overhang_5prime,
                'overhang_3prime': part.overhang_3prime,
                'orientation': orientation,
                'description': part.description if hasattr(part, 'description') and part.description else None
            }
        }
        
        features.append(feature)
        
        # Also include the part's own GenBank features (from the .gb file)
        # adjusted to the correct position in the assembled plasmid
        if hasattr(part, 'features') and part.features:
            for gb_feature in part.features:
                adjusted_feature = {
                    'type': gb_feature.get('type', 'misc_feature'),
                    'start': part_start + gb_feature.get('start', 0),
                    'end': part_start + gb_feature.get('end', 0),
                    'strand': (gb_feature.get('strand', 1) * strand),
                    'label': gb_feature.get('label', ''),
                }
                if adjusted_feature['label']:
                    features.append(adjusted_feature)
        
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
    
    # Otherwise infer from the assembly enzyme (from the sequence if needed)
    enzymes = set(site.get('enzyme', 'BsaI') for site in (backbone.restriction_sites or []))
    if not enzymes:
        enzymes = {s['enzyme'] for s in backbone_slots(backbone)}

    if 'BpiI' in enzymes:
        # BpiI backbone = Level 1 cassettes -> Level 2 plasmid
        return 2
    if 'BsaI' in enzymes or 'BsmBI' in enzymes:
        # BsaI backbone = Level 0 parts -> Level 1 plasmid
        return 1
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

    bb_slots = backbone_slots(backbone)
    if not bb_slots:
        return False, f"Backbone '{backbone.name}' has no valid insertion slots"

    # A single-slot acceptor accepts a chain of cassettes as one insert.
    if len(cassettes) > 1 and len(bb_slots) == 1 and (slots is None or len(set(slots)) == 1):
        try:
            cassettes = [_chain_cassettes(cassettes)]
        except AssemblyError as e:
            return False, str(e)
        slots = [bb_slots[0]['slot_number']]

    # Auto-assign slots if needed
    if slots is None:
        slots = list(range(1, len(cassettes) + 1))

    if len(slots) != len(cassettes):
        return False, f"Number of slots ({len(slots)}) must match number of cassettes ({len(cassettes)})"

    # Check if all slots exist
    available_slots = [s['slot_number'] for s in bb_slots]
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
    
    bb_slots = backbone_slots(backbone)

    # A single-slot acceptor accepts a chain of cassettes as one insert.
    if len(cassettes) > 1 and len(bb_slots) == 1 and (slots is None or len(set(slots)) == 1):
        try:
            cassettes = [_chain_cassettes(cassettes)]
        except AssemblyError as e:
            return {'success': False, 'error': str(e), 'expected_length': 0,
                    'feature_count': 0, 'cassette_positions': []}
        slots = [bb_slots[0]['slot_number']]

    # Calculate expected size
    if slots is None:
        slots = list(range(1, len(cassettes) + 1))

    final_size = len(backbone.sequence)
    cassette_positions = []

    # Handle simplified slot format
    if bb_slots and 'insertion_start' not in bb_slots[0]:
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
            slot_info = next((s for s in bb_slots if s['slot_number'] == slot), None)
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


def assemble_level1_guide_plasmid(
    backbone: Backbone,
    array_sequence: str,
    position: int,
    name: str,
    owner_id: str,
    l2_overhang_5prime: str,
    l2_overhang_3prime: str,
    sub_parts: Optional[List[Dict[str, Any]]] = None,
    guide_cassette_name: Optional[str] = None,
    array_features: Optional[List[Dict[str, Any]]] = None,
) -> FinalPlasmid:
    """
    Assemble a Level 1 guide plasmid by splicing a tRNA-sgRNA guide array into a
    MoClo Level 1 acceptor backbone's cloning slot, and create the resulting
    Level 1 Part (named '<name>_L1') that presents the canonical Level 2 position
    fusion overhangs for the chosen position.

    This is the pragmatic model: rather than simulate the full BsaI digest of the
    circular Level 0 modules, we splice the already-assembled array body into the
    acceptor's BsaI slot window (keeping the slot's 4 bp fusion scars), yielding
    the circular Level 1 plasmid. The downstream Level 2 behaviour is driven by
    the position's canonical BpiI fusion overhangs (TGCC/GCAA ... per the MoClo
    standard), which we attach to the created Level 1 Part so the Level 2
    assembler places the unit correctly.

    Args:
        backbone: the Level 1 acceptor backbone (uploaded pICH47xxx vector).
        array_sequence: the assembled guide-array sequence to insert.
        position: Level 2 position (1-7) this acceptor corresponds to.
        name: base name for the plasmid / Level 1 part.
        owner_id: owner id.
        l2_overhang_5prime / l2_overhang_3prime: canonical Level 2 fusion
            overhangs for `position` (from L2_POSITION_OVERHANGS).
        sub_parts: optional Level 0 breakdown to carry onto the Level 1 part.
        guide_cassette_name: optional source cassette name for lineage.

    Returns:
        The created Level 1 FinalPlasmid. Its metadata['created_part_id'] points
        at the Level 1 Part to use for Level 2 assembly.

    Raises:
        AssemblyError: if the backbone has no usable BsaI cloning slot.
    """
    from app.models.part import Part

    slots = backbone_slots(backbone)
    bsa_slots = [s for s in slots if (s.get('enzyme') == 'BsaI')] or slots
    if not bsa_slots:
        raise AssemblyError(
            f"Level 1 acceptor '{backbone.name}' has no usable cloning slot."
        )
    slot = bsa_slots[0]
    start = slot.get('insertion_start')
    end = slot.get('insertion_end')
    bb = backbone.sequence or ''
    if start is None or end is None or not bb or start >= end or end > len(bb):
        raise AssemblyError(
            f"Level 1 acceptor '{backbone.name}' has an unusable cloning slot window."
        )

    # Splice the array body into the acceptor dropout window. The retained
    # backbone keeps its two 4 bp fusion-scar overhangs (slot_5/slot_3); the
    # array body replaces the dropout between them.
    body = (array_sequence or '').upper()
    assembled = bb[:start] + body + bb[end:]

    # Build GenBank-readable feature annotations for the Level 1 plasmid:
    # (a) backbone features, with any feature after the splice shifted by the
    #     length change (len(body) - dropout length), and features inside the
    #     excised dropout window dropped;
    # (b) the guide-array features, offset to the insertion start.
    delta = len(body) - (end - start)
    merged_features = []
    for f in (backbone.features or []):
        try:
            fs = int(f.get('start', 0)); fe = int(f.get('end', 0))
        except (TypeError, ValueError):
            continue
        if fe <= start:
            merged_features.append(dict(f))                      # before the slot
        elif fs >= end:
            nf = dict(f); nf['start'] = fs + delta; nf['end'] = fe + delta
            merged_features.append(nf)                           # after the slot
        # features overlapping the excised dropout are removed (replaced by insert)
    for f in (array_features or []):
        try:
            fs = int(f.get('start', 0)) + start
            fe = int(f.get('end', 0)) + start
        except (TypeError, ValueError):
            continue
        if fe <= fs:
            continue
        merged_features.append({
            'type': f.get('type', 'misc_feature'),
            'label': f.get('label') or f.get('type') or 'feature',
            'start': fs, 'end': fe, 'strand': f.get('strand', 1),
        })
    merged_features.sort(key=lambda x: x.get('start', 0))

    # Build the Level 1 plasmid metadata (mirrors assemble_plasmid shape so the
    # plasmid detail view / strategy renderer work the same way).
    moclo_level = 1
    metadata = {
        'backbone_name': backbone.name,
        'backbone_id': backbone.id,
        'backbone_plasmid_id': getattr(backbone, 'plasmid_id', None),
        'backbone_size': backbone.size,
        'cassette_names': [guide_cassette_name or name],
        'assembly_method': 'MoClo Golden Gate (Level 0 -> Level 1, BsaI)',
        'moclo_level': moclo_level,
        'l2_position': position,
    }

    # FinalPlasmid.create requires a non-empty cassette_ids list. The guide array
    # is a single spliced unit rather than a stored multi-part Cassette, so we
    # reference a nominal id and carry the Level 0 breakdown via cassette_details
    # (the shape the plasmid detail / strategy renderer consumes).
    nominal_cassette_id = f"guide-array-pos{position}"
    metadata['cassette_details'] = [{
        'cassette_id': nominal_cassette_id,
        'cassette_name': (guide_cassette_name or name),
        'cassette_level': '1',
        'parts': sub_parts or [],
    }]

    plasmid = FinalPlasmid.create(
        name=name,
        owner_id=owner_id,
        backbone_id=backbone.id,
        cassette_ids=[nominal_cassette_id],
        assembled_sequence=assembled,
        features=merged_features,
        metadata=metadata,
    )

    # Create the Level 1 Part that represents this unit for Level 2 assembly.
    # It presents the canonical Level 2 position fusion overhangs. Biological
    # annotations are stored as GenBank-readable `features` (NOT appended to the
    # description); the SUBPARTS block is structured provenance for the assembly
    # strategy, not prose.
    # Short human-readable lineage note, plus a structured SUBPARTS block so the
    # Level 2 assembly strategy can expand this unit's Level 0 provenance
    # (promoter + tRNA-sgRNA modules). The SUBPARTS block is stripped from the
    # GenBank /comment qualifier on export, so it does not clutter the file; the
    # biological annotations live in `features` instead.
    import json as _json
    comments = f"MoClo Level 1 guide unit (position {position}). Assembled into {backbone.name}."
    if sub_parts:
        comments += f"\nSUBPARTS: {_json.dumps(sub_parts)}"

    # Build the Level 1 unit PART that feeds Level 2 assembly. This must be the
    # fragment that a BpiI digest of the Level 1 plasmid RELEASES, i.e. the
    # transcription-unit body flanked by the canonical Level 2 position fusion
    # overhangs (l2_overhang_5prime .. l2_overhang_3prime) — NOT the whole
    # circular plasmid. Storing the whole plasmid as the part sequence made the
    # part's real sequence ends (arbitrary backbone coordinates) disagree with
    # its declared fusion overhangs, so Level 2 chaining used the wrong 4 bp and
    # produced an invalid cassette.
    #
    # The assembled array body carries its own Level 0 (BsaI) fusion overhangs
    # (GGAG .. CGCT) at its ends. The released Level 1 insert replaces those L0
    # overhangs with the Level 2 position overhangs, so:
    #     part_sequence = l2_oh5 + array_body[4:-4] + l2_oh3
    arr = (array_sequence or '').upper()
    inner = arr[4:-4] if len(arr) > 8 else arr
    part_sequence = f"{l2_overhang_5prime}{inner}{l2_overhang_3prime}"

    # Array features are expressed relative to the array sequence (which starts
    # with a 4 bp L0 overhang). In the released part the body is shifted left by
    # 4 (dropped L0 overhang) and right by +len(l2_oh5) (prepended L2 overhang);
    # net shift = len(l2_overhang_5prime) - 4 (== 0 for standard 4 bp overhangs).
    feat_shift = len(l2_overhang_5prime) - 4
    part_len = len(part_sequence)
    part_features = []
    for f in (array_features or []):
        try:
            fs = int(f.get('start', 0)) + feat_shift
            fe = int(f.get('end', 0)) + feat_shift
        except (TypeError, ValueError):
            continue
        # Clamp into the released insert and drop features that fall outside it.
        fs = max(0, fs)
        fe = min(part_len, fe)
        if fe <= fs:
            continue
        part_features.append({
            'type': f.get('type', 'misc_feature'),
            'label': f.get('label') or f.get('type') or 'feature',
            'start': fs, 'end': fe, 'strand': f.get('strand', 1),
        })

    part_name = f"{name}_L1"
    try:
        l1_part = Part.create(
            name=part_name,
            part_type='Coding',
            sequence=part_sequence,
            overhang_5prime=l2_overhang_5prime,
            overhang_3prime=l2_overhang_3prime,
            lab_source=f"Assembled from {backbone.name}",
            contributor=owner_id,
            description=f"Level 1 tRNA-sgRNA guide unit (position {position})",
            level='1',
            unit='gRNA-array',
            comments=comments,
            plasmid_id=plasmid.id,
            features=part_features,
        )
        plasmid.metadata['created_part_id'] = l1_part.id
        plasmid.update()
    except Exception as e:  # noqa: BLE001
        import logging
        logging.warning(f"Failed to create Level 1 part from guide plasmid: {e}")

    return plasmid
