"""
GenBank parser specifically for MoClo parts.

Extracts part information from GenBank files and automatically
detects BsaI sites to determine overhangs and part sequence.
"""

from typing import Dict, Any, Optional, Tuple
from Bio import SeqIO
from Bio.Seq import Seq
from io import StringIO
import re


class PartGenBankError(Exception):
    """Exception raised when part GenBank parsing fails."""
    pass


def parse_part_genbank(file_content: str) -> Dict[str, Any]:
    """
    Parse a GenBank file for a MoClo part.
    
    Automatically detects BsaI sites and extracts the part sequence
    between them, along with the 4bp overhangs.
    
    Args:
        file_content: String content of the GenBank file
        
    Returns:
        Dictionary containing:
            - name: Part name from GenBank ID
            - description: Part description
            - sequence: Part sequence (between BsaI sites, without sites)
            - overhang_5prime: 5' overhang (4bp)
            - overhang_3prime: 3' overhang (4bp)
            - full_sequence: Complete sequence including BsaI sites
            - part_type: Suggested part type (if detectable)
            - organism: Source organism
            - features: List of features within the part
            - metadata: Additional metadata
            
    Raises:
        PartGenBankError: If file cannot be parsed or BsaI sites not found
    """
    try:
        # Parse GenBank file
        handle = StringIO(file_content)
        record = SeqIO.read(handle, "genbank")
        
        # Extract full sequence
        full_sequence = str(record.seq).upper()
        
        # Find BsaI sites and extract part
        part_data = extract_part_from_bsai_sites(full_sequence)
        
        # Extract metadata
        name = record.id or record.name or 'Unknown'
        description = record.description or ''
        organism = record.annotations.get('organism', '')
        
        # Detect part type from features or description
        part_type = detect_part_type(record, description)
        
        # Extract features that fall within the part sequence
        features = extract_part_features(record, part_data['part_start'], part_data['part_end'])
        
        # Extract additional metadata from qualifiers
        metadata = extract_part_metadata(record)
        
        return {
            'name': name,
            'description': description,
            'sequence': part_data['sequence'],
            'overhang_5prime': part_data['overhang_5prime'],
            'overhang_3prime': part_data['overhang_3prime'],
            'full_sequence': full_sequence,
            'part_type': part_type,
            'organism': organism,
            'features': features,
            'metadata': metadata,
            'bsai_sites_found': part_data['sites_found']
        }
        
    except ValueError as e:
        raise PartGenBankError(f"Invalid GenBank format: {str(e)}")
    except Exception as e:
        raise PartGenBankError(f"Failed to parse GenBank file: {str(e)}")


def extract_part_from_bsai_sites(sequence: str) -> Dict[str, Any]:
    """
    Find BsaI sites in sequence and extract the part between them.
    
    BsaI recognition site: GGTCTC (cuts after position 1 on top strand)
    Creates 4bp overhang.
    
    For a typical MoClo part:
    5'-...GGTCTC-N-[4bp overhang]-[PART SEQUENCE]-[4bp overhang]-N-GAGACC...-3'
    
    Handles both linear and circular sequences. Uses site orientation (GGTCTC vs GAGACC)
    to determine directionality, not position.
    
    Args:
        sequence: DNA sequence to search
        
    Returns:
        Dictionary with:
            - sequence: Part sequence (without BsaI sites and overhangs)
            - overhang_5prime: 5' overhang (4bp)
            - overhang_3prime: 3' overhang (4bp)
            - part_start: Start position in full sequence
            - part_end: End position in full sequence
            - sites_found: Number of BsaI sites found
            - is_circular: Whether circular wrapping was used
            
    Raises:
        PartGenBankError: If BsaI sites not found or invalid structure
    """
    # BsaI recognition sequences (forward and reverse complement)
    bsai_forward = 'GGTCTC'
    bsai_reverse = 'GAGACC'
    
    # Find all BsaI sites
    forward_sites = [m.start() for m in re.finditer(bsai_forward, sequence)]
    reverse_sites = [m.start() for m in re.finditer(bsai_reverse, sequence)]
    
    total_sites = len(forward_sites) + len(reverse_sites)
    
    if total_sites == 0:
        raise PartGenBankError(
            "No BsaI sites found in sequence. "
            "MoClo parts should be flanked by BsaI sites (GGTCTC/GAGACC)."
        )
    
    if total_sites < 2:
        raise PartGenBankError(
            f"Only {total_sites} BsaI site found. "
            "MoClo parts require 2 BsaI sites (one on each end)."
        )
    
    # Try to find a valid pair of sites
    # GGTCTC is always the 5' site, GAGACC is always the 3' site
    # Position doesn't matter - orientation determines directionality
    
    valid_pairs = []
    
    # Try all combinations of forward and reverse sites
    for fwd_pos in forward_sites:
        for rev_pos in reverse_sites:
            # Calculate overhang positions
            # 5' overhang: 4bp after GGTCTC site
            overhang_5_start = fwd_pos + 7  # After GGTCTC (6bp) + 1bp spacer
            overhang_5_end = overhang_5_start + 4
            
            # 3' overhang: 4bp before GAGACC site
            # For circular sequences, if GAGACC is near the start, the overhang wraps to the end
            if rev_pos < 4:
                # GAGACC is too close to start, overhang wraps around
                # The 4bp overhang comes from the end of the sequence
                overhang_3_start = len(sequence) - (4 - rev_pos)
                overhang_3_end_wrapped = rev_pos
                # For extraction, we'll handle this specially
                is_overhang_wrapped = True
            else:
                overhang_3_start = rev_pos - 4
                overhang_3_end_wrapped = None
                is_overhang_wrapped = False
            
            overhang_3_end = rev_pos
            
            # Check if overhangs are within sequence bounds
            if not (0 <= overhang_5_start < len(sequence) and
                    0 <= overhang_5_end <= len(sequence) and
                    0 <= overhang_3_start < len(sequence) and
                    0 <= overhang_3_end <= len(sequence)):
                continue
            
            # Calculate BOTH possible part lengths (linear and circular)
            # Choose the configuration that does NOT contain the BsaI sites
            
            if fwd_pos < rev_pos and overhang_5_end <= overhang_3_start and not is_overhang_wrapped:
                # Linear configuration possible: GGTCTC ... GAGACC
                linear_length = overhang_3_start - overhang_5_end
                linear_seq = sequence[overhang_5_end:overhang_3_start]
            else:
                linear_length = None
                linear_seq = None
            
            # Circular configuration: part wraps around
            if is_overhang_wrapped:
                circular_length = (len(sequence) - overhang_5_end) + overhang_3_start
                circular_seq = sequence[overhang_5_end:] + sequence[:overhang_3_start]
            else:
                circular_length = (len(sequence) - overhang_5_end) + overhang_3_start
                circular_seq = sequence[overhang_5_end:] + sequence[:overhang_3_start]
            
            # Check which configuration does NOT contain BsaI sites
            # The correct part should not have GGTCTC or GAGACC in it
            linear_has_sites = False
            circular_has_sites = False
            
            if linear_seq:
                linear_has_sites = 'GGTCTC' in linear_seq.upper() or 'GAGACC' in linear_seq.upper()
            
            if circular_seq:
                circular_has_sites = 'GGTCTC' in circular_seq.upper() or 'GAGACC' in circular_seq.upper()
            
            # Prefer the configuration WITHOUT BsaI sites
            if linear_length is not None and circular_length is not None:
                if not linear_has_sites and circular_has_sites:
                    # Use linear (no sites)
                    use_config = 'linear'
                elif linear_has_sites and not circular_has_sites:
                    # Use circular (no sites)
                    use_config = 'circular'
                else:
                    # Both have sites or both don't - use shorter as fallback
                    use_config = 'linear' if linear_length < circular_length else 'circular'
                
                if use_config == 'linear':
                    valid_pairs.append({
                        'fwd_pos': fwd_pos,
                        'rev_pos': rev_pos,
                        'part_length': linear_length,
                        'overhang_5_start': overhang_5_start,
                        'overhang_5_end': overhang_5_end,
                        'overhang_3_start': overhang_3_start,
                        'overhang_3_end': overhang_3_end,
                        'overhang_3_end_wrapped': None,
                        'is_overhang_wrapped': False,
                        'is_circular': False,
                        'has_internal_sites': linear_has_sites
                    })
                else:
                    valid_pairs.append({
                        'fwd_pos': fwd_pos,
                        'rev_pos': rev_pos,
                        'part_length': circular_length,
                        'overhang_5_start': overhang_5_start,
                        'overhang_5_end': overhang_5_end,
                        'overhang_3_start': overhang_3_start,
                        'overhang_3_end': overhang_3_end,
                        'overhang_3_end_wrapped': overhang_3_end_wrapped,
                        'is_overhang_wrapped': is_overhang_wrapped,
                        'is_circular': True,
                        'has_internal_sites': circular_has_sites
                    })
            elif linear_length is not None:
                # Only linear is possible
                valid_pairs.append({
                    'fwd_pos': fwd_pos,
                    'rev_pos': rev_pos,
                    'part_length': linear_length,
                    'overhang_5_start': overhang_5_start,
                    'overhang_5_end': overhang_5_end,
                    'overhang_3_start': overhang_3_start,
                    'overhang_3_end': overhang_3_end,
                    'overhang_3_end_wrapped': None,
                    'is_overhang_wrapped': False,
                    'is_circular': False,
                    'has_internal_sites': linear_has_sites
                })
            elif circular_length > 0:
                # Only circular is possible
                valid_pairs.append({
                    'fwd_pos': fwd_pos,
                    'rev_pos': rev_pos,
                    'part_length': circular_length,
                    'overhang_5_start': overhang_5_start,
                    'overhang_5_end': overhang_5_end,
                    'overhang_3_start': overhang_3_start,
                    'overhang_3_end': overhang_3_end,
                    'overhang_3_end_wrapped': overhang_3_end_wrapped,
                    'is_overhang_wrapped': is_overhang_wrapped,
                    'is_circular': True,
                    'has_internal_sites': circular_has_sites
                })
    
    if not valid_pairs:
        # No valid pairs found - provide detailed error
        raise PartGenBankError(
            f"Found {len(forward_sites)} GGTCTC site(s) at position(s) {forward_sites} "
            f"and {len(reverse_sites)} GAGACC site(s) at position(s) {reverse_sites}, "
            f"but no valid forward-reverse pair could be formed. "
            f"Sequence length: {len(sequence)}bp. "
            f"This may indicate insufficient sequence data or invalid site positions."
        )
    
    # Prefer configurations WITHOUT internal BsaI sites
    pairs_without_sites = [p for p in valid_pairs if not p.get('has_internal_sites', False)]
    
    if pairs_without_sites:
        # Use the first pair without internal sites
        best_pair = pairs_without_sites[0]
    else:
        # All pairs have internal sites - use the first one
        # (This shouldn't happen for properly designed MoClo parts)
        best_pair = valid_pairs[0]
    
    # Extract overhangs
    overhang_5prime = sequence[best_pair['overhang_5_start']:best_pair['overhang_5_end']]
    
    # Handle wrapped 3' overhang
    if best_pair.get('is_overhang_wrapped', False):
        # 3' overhang wraps from end to start
        overhang_3prime = (sequence[best_pair['overhang_3_start']:] + 
                          sequence[:best_pair['overhang_3_end_wrapped']])
    else:
        overhang_3prime = sequence[best_pair['overhang_3_start']:best_pair['overhang_3_end']]
    
    # Extract part sequence
    if best_pair['is_circular']:
        # Circular: concatenate from GGTCTC to end + from start to GAGACC
        part_sequence = (sequence[best_pair['overhang_5_end']:] + 
                        sequence[:best_pair['overhang_3_start']])
        part_start = best_pair['overhang_5_end']
        part_end = best_pair['overhang_3_start']  # This is in the "wrapped" context
    else:
        # Linear: simple extraction
        part_start = best_pair['overhang_5_end']
        part_end = best_pair['overhang_3_start']
        part_sequence = sequence[part_start:part_end]
    
    # Validate overhangs are 4bp
    if len(overhang_5prime) != 4:
        raise PartGenBankError(
            f"Invalid 5' overhang length: {len(overhang_5prime)}bp (expected 4bp). "
            f"Overhang sequence: '{overhang_5prime}'. "
            f"Check if sequence is complete after GGTCTC site at position {best_pair['fwd_pos']}."
        )
    
    if len(overhang_3prime) != 4:
        raise PartGenBankError(
            f"Invalid 3' overhang length: {len(overhang_3prime)}bp (expected 4bp). "
            f"Overhang sequence: '{overhang_3prime}'. "
            f"Check if there's enough sequence before GAGACC site at position {best_pair['rev_pos']}."
        )
    
    # Validate part sequence exists
    if len(part_sequence) == 0:
        raise PartGenBankError(
            "No sequence found between overhangs. "
            f"The BsaI sites configuration is invalid."
        )
    
    # If multiple valid pairs were found, log a warning
    if len(valid_pairs) > 1:
        import logging
        logging.warning(
            f"Multiple valid BsaI site pairs found ({len(valid_pairs)}). "
            f"Using pair at positions {best_pair['fwd_pos']} (GGTCTC) and {best_pair['rev_pos']} (GAGACC) "
            f"with part length {best_pair['part_length']}bp ({'circular' if best_pair['is_circular'] else 'linear'})."
        )
    
    return {
        'sequence': part_sequence,
        'overhang_5prime': overhang_5prime,
        'overhang_3prime': overhang_3prime,
        'part_start': part_start,
        'part_end': part_end,
        'sites_found': total_sites,
        'is_circular': best_pair['is_circular'],
        'sites_used': f"GGTCTC at {best_pair['fwd_pos']}, GAGACC at {best_pair['rev_pos']}"
    }


def detect_part_type(record, description: str) -> str:
    """
    Attempt to detect the part type from features and description.
    
    Maps detected types to valid Part model types:
    - Coding
    - NonCodingPromoter
    - NonCodingTerminator
    - NonCodingIntron
    - NonCodingOther
    
    Args:
        record: BioPython SeqRecord
        description: Part description
        
    Returns:
        Detected part type or 'NonCodingOther' if unknown
    """
    # Check description for keywords
    desc_lower = description.lower()
    
    # Check for promoter
    if any(kw in desc_lower for kw in ['promoter', 'prom']):
        return 'NonCodingPromoter'
    
    # Check for coding sequence
    if any(kw in desc_lower for kw in ['cds', 'coding sequence', 'orf', 'gene', 'protein']):
        return 'Coding'
    
    # Check for terminator
    if any(kw in desc_lower for kw in ['terminator', 'term']):
        return 'NonCodingTerminator'
    
    # Check for UTRs (treat as NonCodingOther)
    if any(kw in desc_lower for kw in ["5'utr", '5utr', "3'utr", '3utr', 'utr']):
        return 'NonCodingOther'
    
    # Check for intron
    if any(kw in desc_lower for kw in ['intron']):
        return 'NonCodingIntron'
    
    # Check features
    for feature in record.features:
        if feature.type == 'promoter':
            return 'NonCodingPromoter'
        elif feature.type == 'CDS':
            return 'Coding'
        elif feature.type == 'terminator':
            return 'NonCodingTerminator'
        elif feature.type in ["5'UTR", "3'UTR", 'UTR']:
            return 'NonCodingOther'
        elif feature.type == 'intron':
            return 'NonCodingIntron'
    
    # Default to NonCodingOther
    return 'NonCodingOther'


def extract_part_features(record, part_start: int, part_end: int) -> list:
    """
    Extract features that fall within the part sequence.
    
    Args:
        record: BioPython SeqRecord
        part_start: Start position of part in full sequence
        part_end: End position of part in full sequence
        
    Returns:
        List of feature dictionaries with adjusted positions
    """
    features = []
    
    for feature in record.features:
        # Skip source features
        if feature.type == 'source':
            continue
        
        feat_start = int(feature.location.start)
        feat_end = int(feature.location.end)
        
        # Check if feature overlaps with part region
        if feat_start < part_end and feat_end > part_start:
            # Adjust positions relative to part start
            adjusted_start = max(0, feat_start - part_start)
            adjusted_end = min(part_end - part_start, feat_end - part_start)
            
            # Get feature label
            label = ''
            for qualifier in ['label', 'gene', 'product', 'note']:
                if qualifier in feature.qualifiers:
                    value = feature.qualifiers[qualifier]
                    label = value[0] if isinstance(value, list) else str(value)
                    break
            
            if not label:
                label = feature.type
            
            features.append({
                'type': feature.type,
                'start': adjusted_start,
                'end': adjusted_end,
                'strand': feature.location.strand or 1,
                'label': label
            })
    
    return features


def extract_part_metadata(record) -> Dict[str, Any]:
    """
    Extract additional metadata from GenBank record.
    
    Args:
        record: BioPython SeqRecord
        
    Returns:
        Dictionary with metadata fields
    """
    metadata = {}
    
    # Extract from annotations
    if 'organism' in record.annotations:
        metadata['organism'] = record.annotations['organism']
    
    if 'references' in record.annotations and record.annotations['references']:
        ref = record.annotations['references'][0]
        if hasattr(ref, 'title'):
            metadata['reference'] = ref.title
        if hasattr(ref, 'authors'):
            metadata['authors'] = ref.authors
    
    # Look for common qualifiers in features
    for feature in record.features:
        if 'note' in feature.qualifiers:
            notes = feature.qualifiers['note']
            if isinstance(notes, list):
                metadata['notes'] = '; '.join(notes)
            else:
                metadata['notes'] = str(notes)
            break
    
    return metadata


def validate_part_genbank(file_content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that a GenBank file is suitable for part import.
    
    Args:
        file_content: String content to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parse_part_genbank(file_content)
        return True, None
    except PartGenBankError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Validation error: {str(e)}"
