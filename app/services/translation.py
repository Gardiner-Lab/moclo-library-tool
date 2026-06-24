"""
Translation service for analyzing coding sequences in cassettes.

Provides functions to:
- Find start codons (ATG) in sequences
- Translate DNA to protein
- Detect stop codons
- Validate reading frames
"""

from typing import Dict, List, Any, Optional, Tuple


# Standard genetic code
CODON_TABLE = {
    'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L',
    'TCT': 'S', 'TCC': 'S', 'TCA': 'S', 'TCG': 'S',
    'TAT': 'Y', 'TAC': 'Y', 'TAA': '*', 'TAG': '*',
    'TGT': 'C', 'TGC': 'C', 'TGA': '*', 'TGG': 'W',
    'CTT': 'L', 'CTC': 'L', 'CTA': 'L', 'CTG': 'L',
    'CCT': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
    'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
    'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
    'ATT': 'I', 'ATC': 'I', 'ATA': 'I', 'ATG': 'M',
    'ACT': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T',
    'AAT': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K',
    'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
    'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V',
    'GCT': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
    'GAT': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
    'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G'
}

STOP_CODONS = {'TAA', 'TAG', 'TGA'}
START_CODON = 'ATG'


def translate_sequence(dna_sequence: str, start_pos: int = 0) -> str:
    """
    Translate a DNA sequence to protein.
    
    Args:
        dna_sequence: DNA sequence (uppercase ATCG)
        start_pos: Position to start translation (0-indexed)
        
    Returns:
        Protein sequence (single letter amino acid codes)
    """
    protein = []
    
    # Translate in triplets starting from start_pos
    for i in range(start_pos, len(dna_sequence) - 2, 3):
        codon = dna_sequence[i:i+3]
        if len(codon) == 3:
            aa = CODON_TABLE.get(codon, 'X')  # X for unknown
            protein.append(aa)
            if aa == '*':  # Stop codon
                break
    
    return ''.join(protein)


def find_start_codons(sequence: str) -> List[int]:
    """
    Find all ATG start codon positions in a sequence.
    
    Args:
        sequence: DNA sequence (uppercase ATCG)
        
    Returns:
        List of positions where ATG occurs (0-indexed)
    """
    positions = []
    for i in range(len(sequence) - 2):
        if sequence[i:i+3] == START_CODON:
            positions.append(i)
    return positions


def find_stop_codons(sequence: str, start_pos: int = 0) -> List[Tuple[int, str]]:
    """
    Find all stop codons in a sequence from a given position.
    
    Args:
        sequence: DNA sequence (uppercase ATCG)
        start_pos: Position to start searching (0-indexed)
        
    Returns:
        List of tuples (position, codon) for each stop codon found
    """
    stops = []
    
    # Check in-frame stop codons
    for i in range(start_pos, len(sequence) - 2, 3):
        codon = sequence[i:i+3]
        if codon in STOP_CODONS:
            stops.append((i, codon))
    
    return stops


def find_aggt_splice_sites(sequence: str, intron_start_approx: int, intron_end_approx: int, search_window: int = 10) -> Tuple[Optional[int], Optional[int]]:
    """
    Use GenBank annotation positions directly for splice sites.
    
    IMPORTANT: GenBank intron annotations INCLUDE the splice sites (GT and AG) as part
    of the intron. The annotation region should be removed in its entirety:
    - Start position: AT the donor GT (first base of intron, including the GT)
    - End position: AFTER the acceptor AG (first base after intron, after the AG)
    
    Example:
    Sequence: ...TACAGGTAGGTAAA...TTTTAGGTCAA...
              exon1  |intron  |exon2
                     ^start   ^end
    
    The annotation includes GT...AG, so removing [start:end] removes the entire intron
    including both splice sites. After removal:
    Result: ...TACAGGTCAA... (AG from exon1 + GT from exon2 = AGGT reformed)
    
    Args:
        sequence: DNA sequence
        intron_start_approx: Start position from annotation (AT the donor GT)
        intron_end_approx: End position from annotation (AFTER the acceptor AG)
        search_window: Unused, kept for compatibility
        
    Returns:
        Tuple of (intron_start, intron_end) - the annotation positions directly
    """
    # Use annotation positions directly without any correction
    # The GenBank annotations include the GT-AG splice sites and should be removed entirely
    return intron_start_approx, intron_end_approx


def translate_with_splicing(sequence: str, start_pos: int, intron_positions: List[Tuple[int, int]]) -> Tuple[str, str]:
    """
    Translate a sequence after removing specified introns.
    
    Args:
        sequence: DNA sequence
        start_pos: Position where translation starts
        intron_positions: List of (start, end) tuples for introns to remove
        
    Returns:
        Tuple of (protein_sequence, spliced_dna_sequence)
    """
    # Create spliced sequence by removing introns
    spliced_seq = sequence
    
    # Sort introns by position (reverse order to maintain positions)
    sorted_introns = sorted(intron_positions, key=lambda x: x[0], reverse=True)
    
    for intron_start, intron_end in sorted_introns:
        spliced_seq = spliced_seq[:intron_start] + spliced_seq[intron_end:]
    
    # Adjust start position based on removed introns before it
    adjusted_start = start_pos
    for intron_start, intron_end in intron_positions:
        if intron_end <= start_pos:
            adjusted_start -= (intron_end - intron_start)
    
    # Translate the spliced sequence
    protein = translate_sequence(spliced_seq, adjusted_start)
    return protein, spliced_seq


def analyze_coding_sequence(sequence: str, part_boundaries: List[Dict[str, Any]], 
                           user_introns: Optional[List[Dict[str, int]]] = None) -> Dict[str, Any]:
    """
    Analyze a cassette sequence for coding regions.
    
    Only analyzes the coding parts, finding ATG start codons within or just before
    the coding sequence, and translating only the coding regions. Detects introns
    from part annotations and allows user-specified intron positions.
    
    Args:
        sequence: Complete assembled cassette sequence
        part_boundaries: List of dicts with part info including positions and types
        user_introns: Optional list of user-specified intron positions [{'start': int, 'end': int}, ...]
        
    Returns:
        Dictionary with translation analysis:
        {
            'has_coding': bool,
            'start_codon_pos': int or None,
            'protein_sequence': str or None,
            'protein_sequence_spliced': str or None (if introns present),
            'spliced_dna_sequence': str or None (if introns present),
            'stop_codons': list of (position, codon),
            'stop_codons_spliced': list of (position, codon) (if introns present),
            'warnings': list of warning messages,
            'in_frame': bool,
            'coding_region_start': int,
            'coding_region_end': int,
            'has_introns': bool,
            'intron_parts': list of part names,
            'intron_positions': list of {'start': int, 'end': int, 'length': int, 'source': str},
            'has_exons': bool,
            'exon_parts': list of part names,
            'requires_splicing': bool
        }
    """
    result = {
        'has_coding': False,
        'start_codon_pos': None,
        'protein_sequence': None,
        'protein_sequence_spliced': None,
        'spliced_dna_sequence': None,
        'stop_codons': [],
        'stop_codons_spliced': [],
        'warnings': [],
        'in_frame': True,
        'coding_region_start': None,
        'coding_region_end': None,
        'has_introns': False,
        'intron_parts': [],
        'intron_positions': [],
        'has_exons': False,
        'exon_parts': [],
        'requires_splicing': False
    }
    
    # Check if there are any coding parts
    coding_parts = [p for p in part_boundaries if p.get('part_type') == 'Coding']
    if not coding_parts:
        return result
    
    result['has_coding'] = True
    
    # Collect introns from part annotations and user input
    import re
    
    intron_parts = []
    exon_parts = []
    intron_positions = []
    
    for part in part_boundaries:
        part_name = part.get('part_name', '').lower()
        part_type = part.get('part_type', '').lower()
        
        # Check for intron in part name or type (word boundary match)
        # This prevents matching "intronized" or other words containing "intron"
        is_intron_part = False
        if re.search(r'\bintron\b', part_name) or re.search(r'\bintron\b', part_type):
            is_intron_part = True
        
        if is_intron_part:
            intron_parts.append(part.get('part_name'))
            result['has_introns'] = True
            # Record intron position from part boundaries
            intron_positions.append({
                'start': part['start_pos'],
                'end': part['end_pos'],
                'length': part['end_pos'] - part['start_pos'],
                'source': f"part: {part.get('part_name')}"
            })
        
        # Check for intron annotations from GenBank
        if part.get('intron_annotations'):
            for intron_annot in part['intron_annotations']:
                # Convert part-relative positions to cassette-absolute positions
                # For parts after the first one, start_pos includes a 4bp overhang scar
                # but intron annotations are relative to the part sequence (not including scar)
                # So we need to add 4 to skip the scar for non-first parts
                part_index = part_boundaries.index(part)
                scar_offset = 4 if part_index > 0 else 0
                
                abs_start = part['start_pos'] + scar_offset + intron_annot['start']
                abs_end = part['start_pos'] + scar_offset + intron_annot['end']
                intron_positions.append({
                    'start': abs_start,
                    'end': abs_end,
                    'length': intron_annot['length'],
                    'source': f"genbank: {intron_annot.get('name', 'intron')}"
                })
                result['has_introns'] = True
                if intron_annot.get('name'):
                    intron_parts.append(f"{part.get('part_name')} - {intron_annot['name']}")
        
        # Check for exon (word boundary match)
        if re.search(r'\bexon\b', part_name):
            exon_parts.append(part.get('part_name'))
            result['has_exons'] = True
    
    # Add user-specified introns
    if user_introns:
        for intron in user_introns:
            intron_positions.append({
                'start': intron['start'],
                'end': intron['end'],
                'length': intron['end'] - intron['start'],
                'source': 'user-specified'
            })
            result['has_introns'] = True
    
    result['intron_parts'] = intron_parts
    result['exon_parts'] = exon_parts
    result['intron_positions'] = intron_positions
    
    # If introns or exons are present, splicing is required
    if result['has_introns'] or result['has_exons']:
        result['requires_splicing'] = True
        result['warnings'].append(
            'This cassette contains introns/exons and requires RNA splicing for proper translation. '
            'The protein sequence shown is from the genomic DNA and may not represent the final mRNA/protein.'
        )
        
        if result['has_introns']:
            result['warnings'].append(
                f'Intron-containing parts detected: {", ".join(intron_parts)}. '
                'These sequences will be spliced out during mRNA processing in eukaryotic cells.'
            )
        
        if result['has_exons']:
            result['warnings'].append(
                f'Exon-containing parts detected: {", ".join(exon_parts)}. '
                'Only exon sequences will be present in the mature mRNA.'
            )
    
    # Get the coding region boundaries
    first_coding = coding_parts[0]
    last_coding = coding_parts[-1]
    coding_start = first_coding['start_pos']
    coding_end = last_coding['end_pos']
    
    result['coding_region_start'] = coding_start
    result['coding_region_end'] = coding_end
    
    # Extract the coding region (including overhang scars between coding parts)
    coding_sequence = sequence[coding_start:coding_end]
    
    # Look for ATG start codon in the region just before and within the coding sequence
    # Check up to 4bp before (in the overhang scar) and within the first 20bp of coding sequence
    search_start = max(0, coding_start - 4)
    search_end = min(len(sequence), coding_start + 20)
    search_region = sequence[search_start:search_end]
    
    # Find ATG in the search region
    start_positions = find_start_codons(search_region)
    
    if not start_positions:
        result['warnings'].append('No start codon (ATG) found in or near coding sequence')
        result['in_frame'] = False
        return result
    
    # Use the first ATG found
    start_pos_in_search = start_positions[0]
    # Convert to absolute position in full sequence
    start_pos = search_start + start_pos_in_search
    result['start_codon_pos'] = start_pos
    
    # Check if start codon is in frame
    # Calculate offset from coding start
    offset_from_coding_start = start_pos - coding_start
    
    # For proper frame, the offset should be divisible by 3 (or -1, -2, -3, -4 for overhang)
    if offset_from_coding_start >= 0:
        # Start is within coding sequence
        if offset_from_coding_start % 3 != 0:
            result['warnings'].append(
                f'Start codon at position {start_pos} is not in frame with coding sequence (offset: {offset_from_coding_start}bp)'
            )
            result['in_frame'] = False
    else:
        # Start is in overhang scar before coding sequence
        # This is acceptable if it's within 4bp before
        if offset_from_coding_start < -4:
            result['warnings'].append(
                f'Start codon at position {start_pos} is too far before coding sequence'
            )
    
    # Translate from the start codon through the coding region
    # Extract sequence from start codon to end of coding region
    translation_sequence = sequence[start_pos:coding_end]
    protein = translate_sequence(translation_sequence, 0)
    result['protein_sequence'] = protein
    
    # Find stop codons in the translation
    stops = find_stop_codons(translation_sequence, 0)
    # Convert positions to absolute positions in full sequence
    result['stop_codons'] = [(start_pos + pos, codon) for pos, codon in stops]
    
    # If introns are present, perform splicing and re-translate
    if result['has_introns'] and intron_positions:
        # Find actual AGGT splice sites for each intron
        corrected_introns = []
        splice_sites = []
        
        for ip in intron_positions:
            # Use annotation positions directly - no searching or correction
            # The GenBank annotation includes the GT-AG splice sites
            intron_start = ip['start']
            intron_end = ip['end']
            
            corrected_introns.append({
                'start': intron_start,
                'end': intron_end,
                'length': intron_end - intron_start,
                'source': ip['source'],
                'original_start': ip['start'],
                'original_end': ip['end'],
                'corrected': False  # Not corrected, using annotation as-is
            })
            
            # Get splice site context for display
            donor_start = max(0, intron_start - 3)
            donor_end = min(len(sequence), intron_start + 5)
            donor_context = sequence[donor_start:donor_end]
            
            acceptor_start = max(0, intron_end - 5)
            acceptor_end = min(len(sequence), intron_end + 3)
            acceptor_context = sequence[acceptor_start:acceptor_end]
            
            splice_sites.append({
                'intron_name': ip.get('source', 'unknown'),
                'donor_site': donor_context,
                'acceptor_site': acceptor_context,
                'donor_pos': intron_start,
                'acceptor_pos': intron_end,
                'corrected': False
            })
        
        result['splice_sites'] = splice_sites
        result['intron_positions'] = corrected_introns
        
        # Convert intron positions to be relative to translation start
        intron_tuples = [(ip['start'] - start_pos, ip['end'] - start_pos) for ip in corrected_introns]
        
        try:
            spliced_protein, spliced_dna = translate_with_splicing(translation_sequence, 0, intron_tuples)
            result['protein_sequence_spliced'] = spliced_protein
            result['spliced_dna_sequence'] = spliced_dna
            
            # Find stop codons in spliced sequence
            stops_spliced = find_stop_codons(spliced_dna, 0)
            result['stop_codons_spliced'] = [(pos, codon) for pos, codon in stops_spliced]
            
            # Add info message about splicing
            total_intron_length = sum(ip['length'] for ip in corrected_introns)
            corrected_count = sum(1 for ip in corrected_introns if ip.get('corrected', False))
            
            splice_msg = f'Spliced out {len(corrected_introns)} intron(s) totaling {total_intron_length} bp. '
            if corrected_count > 0:
                splice_msg += f'{corrected_count} intron(s) corrected using AGGT splice sites. '
            splice_msg += f'Spliced protein: {len(spliced_protein)} amino acids.'
            
            result['warnings'].append(splice_msg)
        except Exception as e:
            result['warnings'].append(f'Error during splicing: {str(e)}')
    
    # Check for multiple stop codons
    if len(stops) > 1:
        result['warnings'].append(
            f'Multiple stop codons found in genomic sequence: {len(stops)} stop codons at positions {[start_pos + s[0] for s in stops]}'
        )
        
        # If no introns specified, suggest user may need to specify them
        if not result['has_introns']:
            result['warnings'].append(
                'Multiple stop codons detected. If this gene contains introns, please specify their positions '
                'or upload a GenBank file with intron annotations.'
            )
    
    if len(stops) == 0:
        result['warnings'].append('No stop codon found - protein may be incomplete')
    
    # Check if stop codon is premature (before end of coding region)
    if stops:
        first_stop_pos = stops[0][0]  # Position relative to translation start
        first_stop_abs = start_pos + first_stop_pos
        
        # Allow stop codon to be within last 10bp of coding region
        if first_stop_abs < coding_end - 10:
            result['warnings'].append(
                f'Premature stop codon at position {first_stop_abs}, before end of coding sequence at {coding_end}'
            )
    
    return result


def get_part_boundaries_from_cassette(parts: List[Any], assembled_sequence: str) -> List[Dict[str, Any]]:
    """
    Calculate part boundaries in the assembled cassette sequence.
    
    Args:
        parts: List of Part objects in order
        assembled_sequence: Complete assembled sequence
        
    Returns:
        List of dicts with part information and positions
    """
    import json
    import re
    
    boundaries = []
    current_pos = 0
    
    for i, part in enumerate(parts):
        part_start = current_pos
        
        # First part: full sequence
        if i == 0:
            part_length = len(part.sequence)
        else:
            # Subsequent parts: overhang scar (4bp) + part sequence
            part_length = 4 + len(part.sequence)
        
        part_end = part_start + part_length
        
        # Extract intron annotations from comments if present
        intron_annotations = []
        if hasattr(part, 'comments') and part.comments:
            # Look for INTRON_ANNOTATIONS: {...} in comments
            match = re.search(r'INTRON_ANNOTATIONS:\s*(\[.*?\])', part.comments, re.DOTALL)
            if match:
                try:
                    intron_annotations = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        
        boundaries.append({
            'part_id': part.id,
            'part_name': part.name,
            'part_type': part.part_type,
            'start_pos': part_start,
            'end_pos': part_end,
            'length': part_length,
            'intron_annotations': intron_annotations
        })
        
        current_pos = part_end
    
    return boundaries


def analyze_plasmid_translation(plasmid_sequence: str, cassettes: List[Any], 
                                 plasmid_level: int = 2) -> Dict[str, Any]:
    """
    Analyze translation for a multi-level plasmid.
    
    For Level 2+ plasmids, each cassette may contain its own transcription unit
    with an independent reading frame. This function returns per-cassette
    translation data rather than trying to find a single ORF.
    
    For Level 1 cassettes built from Level 0 parts, the original translation
    data computed at assembly time is preserved and returned directly.
    
    Args:
        plasmid_sequence: Complete assembled plasmid sequence
        cassettes: List of Cassette objects used in the assembly
        plasmid_level: MoClo level of the plasmid (1, 2, 3)
        
    Returns:
        Dictionary with multi-frame translation analysis:
        {
            'plasmid_level': int,
            'total_reading_frames': int,
            'transcription_units': [
                {
                    'cassette_id': str,
                    'cassette_name': str,
                    'cassette_level': str,
                    'translation': {...}  # Full translation analysis dict
                },
                ...
            ],
            'warnings': list of str
        }
    """
    result = {
        'plasmid_level': plasmid_level,
        'total_reading_frames': 0,
        'transcription_units': [],
        'warnings': []
    }
    
    if plasmid_level == 1:
        # Level 1 plasmid has a single transcription unit
        # Use the cassette's stored translation data if available
        if cassettes and len(cassettes) == 1:
            cassette = cassettes[0]
            if hasattr(cassette, 'translation_data') and cassette.translation_data:
                result['transcription_units'].append({
                    'cassette_id': cassette.id,
                    'cassette_name': cassette.name,
                    'cassette_level': cassette.level or '1',
                    'translation': cassette.translation_data
                })
                if cassette.translation_data.get('has_coding'):
                    result['total_reading_frames'] = 1
        return result
    
    # Level 2+: each cassette is an independent transcription unit
    for cassette in cassettes:
        tu_entry = {
            'cassette_id': cassette.id,
            'cassette_name': cassette.name,
            'cassette_level': cassette.level or 'unknown',
            'translation': None
        }
        
        # Use persisted translation data from when the cassette was built from Level 0 parts
        if hasattr(cassette, 'translation_data') and cassette.translation_data:
            tu_entry['translation'] = cassette.translation_data
            if cassette.translation_data.get('has_coding'):
                result['total_reading_frames'] += 1
        else:
            # Fallback: re-analyze the cassette sequence
            # This handles older cassettes that don't have stored translation data
            from app.models.part import Part
            parts = []
            for part_id in cassette.part_ids:
                part = Part.get_by_id(part_id)
                if part:
                    parts.append(part)
            
            if parts:
                boundaries = get_part_boundaries_from_cassette(parts, cassette.assembled_sequence)
                translation = analyze_coding_sequence(cassette.assembled_sequence, boundaries)
                tu_entry['translation'] = translation
                if translation.get('has_coding'):
                    result['total_reading_frames'] += 1
        
        result['transcription_units'].append(tu_entry)
    
    if result['total_reading_frames'] > 1:
        result['warnings'].append(
            f'This Level {plasmid_level} plasmid contains {result["total_reading_frames"]} '
            f'independent reading frames from {len(cassettes)} cassettes. '
            f'Each cassette represents a separate transcription unit.'
        )
    elif result['total_reading_frames'] == 0:
        result['warnings'].append(
            f'No coding sequences detected in this Level {plasmid_level} plasmid.'
        )
    
    return result
