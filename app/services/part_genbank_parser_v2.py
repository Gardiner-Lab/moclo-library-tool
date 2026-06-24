"""
Simplified GenBank parser for MoClo parts using overhang-based extraction.

Instead of trying to find the "part" between BsaI sites, we:
1. Find the BsaI sites
2. Extract the overhangs (4bp after GGTCTC, 4bp before GAGACC)
3. Search for those overhang sequences in the full sequence
4. Extract everything between the first occurrence of 5' overhang and first occurrence of 3' overhang
"""

from typing import Dict, Any
from Bio import SeqIO
from io import StringIO
import re


class PartGenBankError(Exception):
    """Exception raised when part GenBank parsing fails."""
    pass


def parse_part_genbank(file_content: str) -> Dict[str, Any]:
    """
    Parse a GenBank file for a MoClo part using overhang-based extraction.
    
    Extracts both the part sequence and plasmid metadata (antibiotic resistance,
    origin of replication, etc.) from the full GenBank file.
    
    Args:
        file_content: String content of the GenBank file
        
    Returns:
        Dictionary with part information and plasmid metadata
    """
    try:
        # Parse GenBank file
        handle = StringIO(file_content)
        record = SeqIO.read(handle, "genbank")
        
        # Extract full sequence
        full_sequence = str(record.seq).upper()
        
        # Find BsaI sites
        bsai_forward = 'GGTCTC'
        bsai_reverse = 'GAGACC'
        
        forward_sites = [m.start() for m in re.finditer(bsai_forward, full_sequence)]
        reverse_sites = [m.start() for m in re.finditer(bsai_reverse, full_sequence)]
        
        if not forward_sites or not reverse_sites:
            raise PartGenBankError(
                f"Need both GGTCTC and GAGACC sites. "
                f"Found {len(forward_sites)} GGTCTC and {len(reverse_sites)} GAGACC."
            )
        
        # Use first forward and first reverse site
        fwd_pos = forward_sites[0]
        rev_pos = reverse_sites[0]
        
        # Extract overhangs
        # 5' overhang: 4bp after GGTCTC (position + 6 for GGTCTC + 1 for spacer)
        overhang_5_start = fwd_pos + 7
        if overhang_5_start + 4 > len(full_sequence):
            raise PartGenBankError("Sequence too short after GGTCTC site")
        overhang_5prime = full_sequence[overhang_5_start:overhang_5_start + 4]
        
        # 3' overhang: 4bp before GAGACC (1bp further toward 5' end)
        if rev_pos < 5:
            # Wraps around
            overhang_3prime = full_sequence[len(full_sequence) - (5 - rev_pos):] + full_sequence[:rev_pos]
            overhang_3prime = overhang_3prime[:4]  # Take only first 4bp
        else:
            overhang_3prime = full_sequence[rev_pos - 5:rev_pos - 1]
        
        # Now find these overhangs in the sequence to determine part boundaries
        # The part starts right after the 5' overhang and ends right before the 3' overhang
        
        # Find 5' overhang (should be right after GGTCTC site)
        part_start = overhang_5_start + 4  # After the 4bp overhang
        
        # Find 3' overhang (1bp further toward 5' end)
        if rev_pos < 5:
            # 3' overhang wraps, so part ends at the position where overhang starts wrapping
            part_end_linear = len(full_sequence) - (5 - rev_pos)
        else:
            part_end_linear = rev_pos - 5
        
        # Extract part sequence
        if part_start < part_end_linear:
            # Linear extraction
            part_sequence = full_sequence[part_start:part_end_linear]
        else:
            # Circular - wraps around
            part_sequence = full_sequence[part_start:] + full_sequence[:part_end_linear]
        
        # Extract metadata from GenBank record
        name = record.id or record.name or 'Unknown'
        description = record.description or ''
        organism = record.annotations.get('organism', '')
        
        # Extract plasmid metadata from features
        plasmid_metadata = extract_plasmid_metadata(record)
        
        # Extract intron annotations
        intron_annotations = extract_intron_annotations(record, part_start, part_end_linear)
        
        # Detect part type
        part_type = detect_part_type(record, description)
        
        return {
            'name': name,
            'description': description,
            'sequence': part_sequence,
            'overhang_5prime': overhang_5prime,
            'overhang_3prime': overhang_3prime,
            'full_sequence': full_sequence,
            'part_type': part_type,
            'organism': organism,
            'features': [],
            'metadata': plasmid_metadata,
            'intron_annotations': intron_annotations,
            'bsai_sites_found': len(forward_sites) + len(reverse_sites),
            'is_circular': part_start >= part_end_linear,
            # Plasmid-specific fields
            'antibiotic': plasmid_metadata.get('antibiotic'),
            'plasmid_size': len(full_sequence),
            'ori_ecoli': plasmid_metadata.get('ori_ecoli'),
            'ori_agro': plasmid_metadata.get('ori_agro'),
            'host_strain': plasmid_metadata.get('host_strain'),
            'reference': plasmid_metadata.get('reference'),
            'comments': plasmid_metadata.get('comments')
        }
        
    except ValueError as e:
        raise PartGenBankError(f"Invalid GenBank format: {str(e)}")
    except Exception as e:
        raise PartGenBankError(f"Failed to parse GenBank file: {str(e)}")


def extract_intron_annotations(record, part_start: int, part_end: int) -> list:
    """
    Extract intron annotations from GenBank features.
    
    Looks for features with type 'intron' or features with 'intron' in their name/label.
    Returns positions relative to the part sequence (not the full plasmid).
    
    Args:
        record: BioPython SeqRecord object
        part_start: Start position of part in full sequence
        part_end: End position of part in full sequence
        
    Returns:
        List of intron dictionaries with start, end, and name
    """
    import re
    
    introns = []
    
    for feature in record.features:
        feature_type = feature.type.lower()
        qualifiers = feature.qualifiers
        
        # Check if this is an intron feature
        is_intron = False
        intron_name = None
        
        # Check feature type
        if feature_type == 'intron':
            is_intron = True
            # Try to get a better name from qualifiers
            for qual_key in ['label', 'gene', 'product', 'note']:
                if qual_key in qualifiers:
                    intron_name = ' '.join(qualifiers[qual_key])
                    break
            if not intron_name:
                intron_name = 'intron'
        
        # Check qualifiers for intron keywords (case-insensitive, word boundary)
        if not is_intron:
            for qual_key in ['label', 'gene', 'product', 'note']:
                if qual_key in qualifiers:
                    qual_value_original = ' '.join(qualifiers[qual_key])
                    qual_value_lower = qual_value_original.lower()
                    # Use word boundary regex to match "intron" as a standalone word
                    # This prevents matching "intronized", "introns", etc.
                    if re.search(r'\bintron\b', qual_value_lower):
                        is_intron = True
                        intron_name = qual_value_original  # Preserve original case
                        break
        
        if is_intron:
            # Get feature location
            location = feature.location
            intron_start = int(location.start)
            intron_end = int(location.end)
            
            # If part boundaries are defined, check if intron is within them
            # Otherwise, include all introns (they'll be relative to full sequence)
            if part_start is not None and part_end is not None:
                # Check if intron overlaps with the part boundaries
                # Allow partial overlaps to catch edge cases
                if (intron_start < part_end and intron_end > part_start):
                    # Clip to part boundaries if needed
                    relative_start = max(0, intron_start - part_start)
                    relative_end = min(part_end - part_start, intron_end - part_start)
                    
                    # Only add if there's actual overlap
                    if relative_end > relative_start:
                        introns.append({
                            'start': relative_start,
                            'end': relative_end,
                            'length': relative_end - relative_start,
                            'name': intron_name or 'intron',
                            'source': 'genbank_annotation'
                        })
            else:
                # No part boundaries defined, use absolute positions
                # These will need to be adjusted later when part is assembled
                introns.append({
                    'start': intron_start,
                    'end': intron_end,
                    'length': intron_end - intron_start,
                    'name': intron_name or 'intron',
                    'source': 'genbank_annotation'
                })
    
    return introns


def extract_plasmid_metadata(record) -> Dict[str, Any]:
    """
    Extract plasmid metadata from GenBank features.
    
    Looks for antibiotic resistance markers, origins of replication,
    and other relevant plasmid information.
    
    Args:
        record: BioPython SeqRecord object
        
    Returns:
        Dictionary with plasmid metadata
    """
    metadata = {
        'antibiotic': None,
        'ori_ecoli': None,
        'ori_agro': None,
        'host_strain': None,
        'reference': None,
        'comments': None
    }
    
    # Common antibiotic resistance markers
    antibiotic_markers = {
        'kan': 'Kanamycin',
        'kana': 'Kanamycin',
        'kanamycin': 'Kanamycin',
        'kanr': 'Kanamycin',
        'amp': 'Ampicillin',
        'ampr': 'Ampicillin',
        'ampicillin': 'Ampicillin',
        'tet': 'Tetracycline',
        'tetr': 'Tetracycline',
        'tetracycline': 'Tetracycline',
        'spec': 'Spectinomycin',
        'spectinomycin': 'Spectinomycin',
        'strep': 'Streptomycin',
        'streptomycin': 'Streptomycin',
        'chlor': 'Chloramphenicol',
        'chloramphenicol': 'Chloramphenicol',
        'gent': 'Gentamicin',
        'gentamicin': 'Gentamicin',
        'hyg': 'Hygromycin',
        'hygromycin': 'Hygromycin',
        'basta': 'Basta',
        'bar': 'Basta',
        'ery': 'Erythromycin',
        'erythromycin': 'Erythromycin'
    }
    
    # Common E. coli origins
    ecoli_origins = ['pBR322', 'ColE1', 'pUC', 'p15A', 'pSC101', 'R6K']
    
    # Common Agrobacterium origins
    agro_origins = ['pVS1', 'pRK2', 'pSa', 'pRi']
    
    antibiotics_found = []
    ori_ecoli_found = []
    ori_agro_found = []
    comments_list = []
    
    # Search through features
    for feature in record.features:
        feature_type = feature.type.lower()
        qualifiers = feature.qualifiers
        
        # Check for antibiotic resistance
        if feature_type in ['CDS', 'gene', 'misc_feature']:
            # Check gene name
            if 'gene' in qualifiers:
                gene_name = ' '.join(qualifiers['gene']).lower()
                for marker, antibiotic in antibiotic_markers.items():
                    if marker in gene_name and antibiotic not in antibiotics_found:
                        antibiotics_found.append(antibiotic)
            
            # Check product
            if 'product' in qualifiers:
                product = ' '.join(qualifiers['product']).lower()
                for marker, antibiotic in antibiotic_markers.items():
                    if marker in product and antibiotic not in antibiotics_found:
                        antibiotics_found.append(antibiotic)
                
                # Check for resistance in product name
                if 'resistance' in product:
                    for marker, antibiotic in antibiotic_markers.items():
                        if marker in product and antibiotic not in antibiotics_found:
                            antibiotics_found.append(antibiotic)
            
            # Check label
            if 'label' in qualifiers:
                label = ' '.join(qualifiers['label']).lower()
                for marker, antibiotic in antibiotic_markers.items():
                    if marker in label and antibiotic not in antibiotics_found:
                        antibiotics_found.append(antibiotic)
        
        # Check for origin of replication
        if feature_type in ['rep_origin', 'misc_feature', 'origin']:
            # Check label
            if 'label' in qualifiers:
                label = ' '.join(qualifiers['label'])
                for ori in ecoli_origins:
                    if ori in label and ori not in ori_ecoli_found:
                        ori_ecoli_found.append(ori)
                for ori in agro_origins:
                    if ori in label and ori not in ori_agro_found:
                        ori_agro_found.append(ori)
            
            # Check note
            if 'note' in qualifiers:
                note = ' '.join(qualifiers['note'])
                for ori in ecoli_origins:
                    if ori in note and ori not in ori_ecoli_found:
                        ori_ecoli_found.append(ori)
                for ori in agro_origins:
                    if ori in note and ori not in ori_agro_found:
                        ori_agro_found.append(ori)
        
        # Collect notes and comments
        if 'note' in qualifiers:
            note = ' '.join(qualifiers['note'])
            if note and note not in comments_list:
                comments_list.append(note)
    
    # Check annotations for additional info
    if 'comment' in record.annotations:
        comment = record.annotations['comment']
        if comment:
            comments_list.append(comment)
    
    if 'references' in record.annotations and record.annotations['references']:
        refs = []
        for ref in record.annotations['references']:
            if hasattr(ref, 'title') and ref.title:
                refs.append(ref.title)
            elif hasattr(ref, 'journal') and ref.journal:
                refs.append(ref.journal)
        if refs:
            metadata['reference'] = '; '.join(refs[:2])  # Limit to first 2 references
    
    # Set metadata
    if antibiotics_found:
        metadata['antibiotic'] = ', '.join(antibiotics_found)
    
    if ori_ecoli_found:
        metadata['ori_ecoli'] = ', '.join(ori_ecoli_found)
    
    if ori_agro_found:
        metadata['ori_agro'] = ', '.join(ori_agro_found)
    
    if comments_list:
        # Limit comments to reasonable length
        all_comments = '; '.join(comments_list)
        metadata['comments'] = all_comments[:500] if len(all_comments) > 500 else all_comments
    
    return metadata


def detect_part_type(record, description: str) -> str:
    """Detect part type from features and description."""
    desc_lower = description.lower()
    
    if any(kw in desc_lower for kw in ['promoter', 'prom']):
        return 'NonCodingPromoter'
    elif any(kw in desc_lower for kw in ['cds', 'coding sequence', 'orf', 'gene', 'protein']):
        return 'Coding'
    elif any(kw in desc_lower for kw in ['terminator', 'term']):
        return 'NonCodingTerminator'
    elif any(kw in desc_lower for kw in ['intron']):
        return 'NonCodingIntron'
    
    for feature in record.features:
        if feature.type == 'promoter':
            return 'NonCodingPromoter'
        elif feature.type == 'CDS':
            return 'Coding'
        elif feature.type == 'terminator':
            return 'NonCodingTerminator'
        elif feature.type == 'intron':
            return 'NonCodingIntron'
    
    return 'NonCodingOther'
