"""
Restriction site finder for MoClo assembly.

This module provides functions to find and analyze restriction enzyme
sites used in MoClo assembly (BsaI, BpiI/BbsI, BsmBI).
"""

import re
from typing import List, Dict, Any, Optional, Tuple


# MoClo restriction enzyme recognition sequences
MOCLO_ENZYMES = {
    'BsaI': {
        'recognition': 'GGTCTC',
        'cut_pattern': 'GGTCTC(N)1/5',  # Cuts 1 base on top strand, 5 on bottom
        'overhang_length': 4
    },
    'BpiI': {  # Also known as BbsI
        'recognition': 'GAAGAC',
        'cut_pattern': 'GAAGAC(N)2/6',  # Cuts 2 bases on top strand, 6 on bottom
        'overhang_length': 4
    },
    'BsmBI': {
        'recognition': 'CGTCTC',
        'cut_pattern': 'CGTCTC(N)1/5',  # Cuts 1 base on top strand, 5 on bottom
        'overhang_length': 4
    }
}


def find_moclo_sites(
    sequence: str,
    enzyme: str = 'BsaI',
    include_reverse: bool = True
) -> List[Dict[str, Any]]:
    """
    Find all MoClo restriction sites in a sequence.
    
    Args:
        sequence: DNA sequence to search
        enzyme: Enzyme name ('BsaI', 'BpiI', or 'BsmBI')
        include_reverse: Whether to search reverse complement
        
    Returns:
        List of site dictionaries with:
            - enzyme: Enzyme name
            - position: Position in sequence (0-indexed)
            - strand: 'forward' or 'reverse'
            - recognition_site: Recognition sequence
            - overhang_5prime: 5' overhang after digestion
            - overhang_3prime: 3' overhang after digestion
            
    Raises:
        ValueError: If enzyme is not recognized
    """
    if enzyme not in MOCLO_ENZYMES:
        raise ValueError(f"Unknown enzyme: {enzyme}. Must be one of {list(MOCLO_ENZYMES.keys())}")
    
    enzyme_info = MOCLO_ENZYMES[enzyme]
    recognition = enzyme_info['recognition']
    
    sites = []
    sequence = sequence.upper()
    
    # Find forward strand sites
    sites.extend(_find_sites_on_strand(sequence, enzyme, recognition, 'forward'))
    
    # Find reverse strand sites
    if include_reverse:
        reverse_comp = reverse_complement(sequence)
        reverse_sites = _find_sites_on_strand(reverse_comp, enzyme, recognition, 'reverse')
        
        # Adjust positions for reverse strand
        for site in reverse_sites:
            site['position'] = len(sequence) - site['position'] - len(recognition)
        
        sites.extend(reverse_sites)
    
    # Sort by position
    sites.sort(key=lambda x: x['position'])
    
    return sites


def _find_sites_on_strand(
    sequence: str,
    enzyme: str,
    recognition: str,
    strand: str
) -> List[Dict[str, Any]]:
    """
    Find restriction sites on a single strand.
    
    Args:
        sequence: DNA sequence
        enzyme: Enzyme name
        recognition: Recognition sequence
        strand: 'forward' or 'reverse'
        
    Returns:
        List of site dictionaries
    """
    sites = []
    
    # Find all occurrences of recognition sequence
    for match in re.finditer(recognition, sequence):
        position = match.start()
        
        # Calculate overhangs
        overhangs = _calculate_overhangs(sequence, position, enzyme, strand)
        
        if overhangs:
            # Store the overhang - for both forward and reverse, we now get the same value
            # which represents the overhang sequence at this cut site
            site = {
                'enzyme': enzyme,
                'position': position,
                'strand': strand,
                'recognition_site': recognition,
                'overhang_5prime': overhangs[0],
                'overhang_3prime': overhangs[1]
            }
            sites.append(site)
    
    return sites


def _calculate_overhangs(
    sequence: str,
    position: int,
    enzyme: str,
    strand: str
) -> Optional[Tuple[str, str]]:
    """
    Calculate the 4bp overhangs created after enzyme digestion.
    
    For BsaI: GGTCTC N^NNNN (cuts after recognition + 1bp)
    For BpiI: GAAGAC NN^NNNN (cuts after recognition + 2bp)
    For BsmBI: CGTCTC N^NNNN (cuts after recognition + 1bp)
    
    Args:
        sequence: DNA sequence
        position: Position of recognition site
        enzyme: Enzyme name
        strand: 'forward' or 'reverse'
        
    Returns:
        Tuple of (5' overhang, 3' overhang) or None if insufficient sequence
    """
    enzyme_info = MOCLO_ENZYMES[enzyme]
    recognition = enzyme_info['recognition']
    
    # Determine cut position offset
    if enzyme == 'BsaI' or enzyme == 'BsmBI':
        cut_offset = 1  # Cuts 1 base after recognition
    elif enzyme == 'BpiI':
        cut_offset = 2  # Cuts 2 bases after recognition
    else:
        return None
    
    # Calculate positions
    rec_end = position + len(recognition)
    cut_pos = rec_end + cut_offset
    overhang_end = cut_pos + 4
    
    # Check if we have enough sequence
    if overhang_end > len(sequence):
        return None
    
    # Extract overhang sequence
    overhang = sequence[cut_pos:overhang_end]
    
    if len(overhang) != 4:
        return None
    
    if strand == 'forward':
        # For forward strand, the overhang sequence after the cut is the 3' overhang
        # This overhang will be on the 5' side of the insertion site
        return (overhang, overhang)
    else:
        # For reverse strand, reverse complement the overhang
        # This overhang will be on the 3' side of the insertion site
        overhang_rc = reverse_complement(overhang)
        return (overhang_rc, overhang_rc)


def identify_cassette_slots(sites: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identify cassette insertion slots from restriction sites.
    
    A cassette slot consists of two restriction sites that flank
    an insertion region. The sites should be in opposite orientations.
    
    Args:
        sites: List of restriction site dictionaries
        
    Returns:
        List of slot dictionaries with:
            - slot_number: Slot identifier (1, 2, 3, ...)
            - site_5prime: 5' restriction site
            - site_3prime: 3' restriction site
            - expected_overhang_5prime: Expected 5' overhang for cassette
            - expected_overhang_3prime: Expected 3' overhang for cassette
            - insertion_start: Start position for insertion
            - insertion_end: End position for insertion
    """
    if len(sites) < 2:
        return []
    
    slots = []
    slot_number = 1
    
    # Group sites into pairs
    # In MoClo, sites typically come in pairs flanking insertion regions
    i = 0
    while i < len(sites) - 1:
        site1 = sites[i]
        site2 = sites[i + 1]
        
        # Check if sites are in opposite orientations (typical for MoClo)
        if site1['strand'] != site2['strand']:
            # This is likely a cassette slot
            slot = _create_slot_from_sites(site1, site2, slot_number)
            if slot:  # Only add if slot creation succeeded
                slots.append(slot)
                slot_number += 1
            i += 2  # Skip both sites
        else:
            i += 1
    
    return slots


def _create_slot_from_sites(
    site1: Dict[str, Any],
    site2: Dict[str, Any],
    slot_number: int
) -> Optional[Dict[str, Any]]:
    """
    Create a cassette slot from two restriction sites.
    
    In MoClo, a cassette insertion slot is formed by two restriction sites
    in opposite orientations. The forward site creates the 5' overhang,
    and the reverse site creates the 3' overhang.
    
    Args:
        site1: First restriction site
        site2: Second restriction site
        slot_number: Slot identifier
        
    Returns:
        Slot dictionary or None if overhangs cannot be determined
    """
    # Determine which site is 5' and which is 3' based on position
    if site1['position'] < site2['position']:
        site_5prime = site1
        site_3prime = site2
    else:
        site_5prime = site2
        site_3prime = site1
    
    # Calculate insertion region
    rec_site = site_5prime.get('recognition_site')
    if rec_site:
        rec_len = len(rec_site)
    else:
        # Fall back to enzyme recognition length from MOCLO_ENZYMES
        enzyme = site_5prime.get('enzyme', 'BsaI')
        rec_len = len(MOCLO_ENZYMES.get(enzyme, {}).get('recognition', 'GGTCTC'))
    insertion_start = site_5prime['position'] + rec_len
    insertion_end = site_3prime['position']
    
    # Determine expected overhangs for cassette based on strand orientation
    # For MoClo Golden Gate assembly:
    # - The 5' site (typically reverse strand) provides the 5' overhang for the cassette
    # - The 3' site (typically forward strand) provides the 3' overhang for the cassette
    # 
    # For reverse strand sites: use overhang_5prime (the overhang on the 5' side after digestion)
    # For forward strand sites: use overhang_3prime (the overhang on the 3' side after digestion)
    
    # Get the correct overhang from each site based on its strand
    if site_5prime['strand'] == 'reverse':
        overhang_5prime_val = site_5prime.get('overhang_5prime', 'NNNN')
    else:
        overhang_5prime_val = site_5prime.get('overhang_3prime', 'NNNN')
    
    if site_3prime['strand'] == 'forward':
        overhang_3prime_val = site_3prime.get('overhang_3prime', 'NNNN')
    else:
        overhang_3prime_val = site_3prime.get('overhang_5prime', 'NNNN')
    
    # If we don't have valid overhangs, return None
    if not overhang_5prime_val or not overhang_3prime_val:
        return None
    
    # Validate overhangs are 4 bases
    if len(overhang_5prime_val) != 4 or len(overhang_3prime_val) != 4:
        return None
    
    return {
        'slot_number': slot_number,
        'site_5prime': site_5prime,
        'site_3prime': site_3prime,
        'expected_overhang_5prime': overhang_5prime_val,
        'expected_overhang_3prime': overhang_3prime_val,
        'insertion_start': insertion_start,
        'insertion_end': insertion_end,
        'insertion_length': insertion_end - insertion_start
    }


def get_insertion_overhangs(
    sequence: str,
    site: Dict[str, Any]
) -> Tuple[str, str]:
    """
    Get the overhangs at an insertion site after digestion.
    
    Args:
        sequence: DNA sequence
        site: Restriction site dictionary
        
    Returns:
        Tuple of (5' overhang, 3' overhang)
    """
    enzyme = site['enzyme']
    position = site['position']
    strand = site['strand']
    
    overhangs = _calculate_overhangs(sequence, position, enzyme, strand)
    
    if overhangs:
        return overhangs
    
    return ('NNNN', 'NNNN')


def reverse_complement(sequence: str) -> str:
    """
    Get the reverse complement of a DNA sequence.
    
    Args:
        sequence: DNA sequence
        
    Returns:
        Reverse complement sequence
    """
    complement = {
        'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C',
        'R': 'Y', 'Y': 'R', 'S': 'S', 'W': 'W',
        'K': 'M', 'M': 'K', 'B': 'V', 'V': 'B',
        'D': 'H', 'H': 'D', 'N': 'N'
    }
    
    return ''.join(complement.get(base, base) for base in reversed(sequence.upper()))


def annotate_sites_in_sequence(
    sequence: str,
    sites: List[Dict[str, Any]]
) -> str:
    """
    Create an annotated sequence showing restriction sites.
    
    Args:
        sequence: DNA sequence
        sites: List of restriction sites
        
    Returns:
        Annotated sequence string with sites marked
    """
    if not sites:
        return sequence
    
    # Create a list to build annotated sequence
    result = []
    last_pos = 0
    
    for site in sorted(sites, key=lambda x: x['position']):
        pos = site['position']
        rec_len = len(site['recognition_site'])
        
        # Add sequence before site
        result.append(sequence[last_pos:pos])
        
        # Add annotated site
        result.append(f"[{site['enzyme']}:{sequence[pos:pos+rec_len]}]")
        
        last_pos = pos + rec_len
    
    # Add remaining sequence
    result.append(sequence[last_pos:])
    
    return ''.join(result)


def validate_moclo_backbone(
    sequence: str,
    enzyme: str = 'BsaI',
    min_sites: int = 2
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Validate that a sequence is suitable as a MoClo backbone.
    
    Args:
        sequence: DNA sequence to validate
        enzyme: Expected restriction enzyme
        min_sites: Minimum number of sites required
        
    Returns:
        Tuple of (is_valid, message, sites)
    """
    try:
        sites = find_moclo_sites(sequence, enzyme)
        
        if len(sites) < min_sites:
            return (
                False,
                f"Insufficient {enzyme} sites found. Expected at least {min_sites}, found {len(sites)}",
                sites
            )
        
        # Check if sites can form cassette slots
        slots = identify_cassette_slots(sites)
        
        if not slots:
            return (
                False,
                f"Found {len(sites)} {enzyme} sites but they don't form valid cassette insertion slots",
                sites
            )
        
        return (
            True,
            f"Valid MoClo backbone with {len(slots)} cassette slot(s)",
            sites
        )
        
    except Exception as e:
        return (False, f"Validation error: {str(e)}", [])
