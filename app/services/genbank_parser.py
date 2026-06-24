"""
GenBank file parser for extracting plasmid information.

This module provides functions to parse GenBank files and extract
sequence data, features, and metadata for MoClo backbones.
"""

from typing import Dict, List, Any, Optional
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature
from io import StringIO


class GenBankParseError(Exception):
    """Exception raised when GenBank parsing fails."""
    pass


def parse_genbank_file(file_content: str) -> Dict[str, Any]:
    """
    Parse a GenBank file and extract all relevant information.
    
    Args:
        file_content: String content of the GenBank file
        
    Returns:
        Dictionary containing:
            - sequence: DNA sequence string
            - name: Sequence name/ID
            - description: Sequence description
            - features: List of feature dictionaries
            - metadata: Additional metadata
            
    Raises:
        GenBankParseError: If file cannot be parsed
    """
    try:
        # Parse GenBank file
        handle = StringIO(file_content)
        record = SeqIO.read(handle, "genbank")
        
        # Extract all components
        return {
            'sequence': extract_sequence(record),
            'name': record.id or record.name or 'Unknown',
            'description': record.description or '',
            'features': extract_features(record),
            'metadata': extract_metadata(record)
        }
        
    except ValueError as e:
        raise GenBankParseError(f"Invalid GenBank format: {str(e)}")
    except Exception as e:
        raise GenBankParseError(f"Failed to parse GenBank file: {str(e)}")


def extract_sequence(record: SeqRecord) -> str:
    """
    Extract the DNA sequence from a GenBank record.
    
    Args:
        record: BioPython SeqRecord object
        
    Returns:
        DNA sequence as uppercase string
    """
    return str(record.seq).upper()


def extract_features(record: SeqRecord) -> List[Dict[str, Any]]:
    """
    Extract all features from a GenBank record.
    
    Features include CDS, promoters, terminators, resistance markers,
    origins of replication, and other annotated elements.
    
    Args:
        record: BioPython SeqRecord object
        
    Returns:
        List of feature dictionaries with:
            - type: Feature type (CDS, promoter, etc.)
            - start: Start position (0-indexed)
            - end: End position (0-indexed)
            - strand: +1 for forward, -1 for reverse
            - label: Feature label/name
            - qualifiers: Additional feature qualifiers
    """
    features = []
    
    for feature in record.features:
        # Skip source features (they span the entire sequence)
        if feature.type == 'source':
            continue
        
        # Extract feature information
        feature_dict = {
            'type': feature.type,
            'start': int(feature.location.start),
            'end': int(feature.location.end),
            'strand': feature.location.strand or 1,
            'label': _get_feature_label(feature),
            'qualifiers': _extract_qualifiers(feature)
        }
        
        features.append(feature_dict)
    
    return features


def _get_feature_label(feature: SeqFeature) -> str:
    """
    Get a human-readable label for a feature.
    
    Tries multiple qualifier fields in order of preference:
    label, gene, product, note
    
    Args:
        feature: BioPython SeqFeature object
        
    Returns:
        Feature label string
    """
    # Try different qualifier fields
    for qualifier in ['label', 'gene', 'product', 'note']:
        if qualifier in feature.qualifiers:
            value = feature.qualifiers[qualifier]
            if isinstance(value, list):
                return value[0]
            return str(value)
    
    # Fallback to feature type
    return feature.type


def _extract_qualifiers(feature: SeqFeature) -> Dict[str, Any]:
    """
    Extract all qualifiers from a feature.
    
    Args:
        feature: BioPython SeqFeature object
        
    Returns:
        Dictionary of qualifier key-value pairs
    """
    qualifiers = {}
    
    for key, value in feature.qualifiers.items():
        # Convert lists to single values if only one item
        if isinstance(value, list):
            qualifiers[key] = value[0] if len(value) == 1 else value
        else:
            qualifiers[key] = value
    
    return qualifiers


def extract_metadata(record: SeqRecord) -> Dict[str, Any]:
    """
    Extract metadata from a GenBank record.
    
    Args:
        record: BioPython SeqRecord object
        
    Returns:
        Dictionary with metadata including:
            - organism: Source organism
            - topology: linear or circular
            - molecule_type: DNA, RNA, etc.
            - date: Date of record
            - accession: Accession number
    """
    metadata = {
        'organism': '',
        'topology': 'circular',  # Default for plasmids
        'molecule_type': 'DNA',
        'date': '',
        'accession': ''
    }
    
    # Extract from annotations
    annotations = record.annotations
    
    if 'organism' in annotations:
        metadata['organism'] = annotations['organism']
    
    if 'topology' in annotations:
        metadata['topology'] = annotations['topology']
    
    if 'molecule_type' in annotations:
        metadata['molecule_type'] = annotations['molecule_type']
    
    if 'date' in annotations:
        metadata['date'] = annotations['date']
    
    if 'accessions' in annotations and annotations['accessions']:
        metadata['accession'] = annotations['accessions'][0]
    
    return metadata


def validate_genbank_content(file_content: str) -> tuple[bool, Optional[str]]:
    """
    Validate that a file contains valid GenBank format.
    
    Args:
        file_content: String content to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if valid GenBank format
        - error_message: None if valid, error description if invalid
    """
    try:
        handle = StringIO(file_content)
        record = SeqIO.read(handle, "genbank")
        
        # Check for required components
        if not record.seq or len(record.seq) == 0:
            return False, "GenBank file contains no sequence"
        
        # Check sequence contains only valid DNA bases
        valid_bases = set('ATCGRYSWKMBDHVN')
        sequence = str(record.seq).upper()
        invalid_bases = set(sequence) - valid_bases
        
        if invalid_bases:
            return False, f"Sequence contains invalid bases: {', '.join(invalid_bases)}"
        
        return True, None
        
    except ValueError as e:
        return False, f"Invalid GenBank format: {str(e)}"
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def get_feature_sequence(record: SeqRecord, feature: SeqFeature) -> str:
    """
    Extract the sequence for a specific feature.
    
    Args:
        record: BioPython SeqRecord object
        feature: BioPython SeqFeature object
        
    Returns:
        DNA sequence of the feature
    """
    return str(feature.extract(record.seq)).upper()


def find_features_by_type(features: List[Dict[str, Any]], feature_type: str) -> List[Dict[str, Any]]:
    """
    Find all features of a specific type.
    
    Args:
        features: List of feature dictionaries
        feature_type: Type to search for (e.g., 'CDS', 'promoter')
        
    Returns:
        List of matching features
    """
    return [f for f in features if f['type'].lower() == feature_type.lower()]


def get_resistance_markers(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Find antibiotic resistance markers in features.
    
    Looks for CDS features with resistance-related annotations.
    
    Args:
        features: List of feature dictionaries
        
    Returns:
        List of resistance marker features
    """
    resistance_keywords = [
        'resistance', 'resistant', 'ampicillin', 'kanamycin',
        'chloramphenicol', 'tetracycline', 'amp', 'kan', 'cam', 'tet'
    ]
    
    markers = []
    for feature in features:
        if feature['type'] != 'CDS':
            continue
        
        # Check label and qualifiers for resistance keywords
        label = feature['label'].lower()
        qualifiers_str = str(feature['qualifiers']).lower()
        
        if any(keyword in label or keyword in qualifiers_str for keyword in resistance_keywords):
            markers.append(feature)
    
    return markers


def get_origins_of_replication(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Find origins of replication in features.
    
    Args:
        features: List of feature dictionaries
        
    Returns:
        List of origin features
    """
    origins = []
    
    for feature in features:
        if feature['type'] in ['rep_origin', 'origin']:
            origins.append(feature)
        elif 'ori' in feature['label'].lower():
            origins.append(feature)
    
    return origins


def format_genbank_output(
    name: str,
    sequence: str,
    features: List[Dict[str, Any]],
    description: str = "",
    topology: str = "circular"
) -> str:
    """
    Format data back into GenBank format.
    
    Args:
        name: Sequence name
        sequence: DNA sequence
        features: List of feature dictionaries
        description: Sequence description
        topology: 'circular' or 'linear'
        
    Returns:
        GenBank formatted string
    """
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord
    from Bio.SeqFeature import SeqFeature, FeatureLocation
    
    # Create sequence record
    seq_obj = Seq(sequence)
    record = SeqRecord(
        seq_obj,
        id=name,
        name=name,
        description=description
    )
    
    # Set topology
    record.annotations['topology'] = topology
    record.annotations['molecule_type'] = 'DNA'
    
    # Add features
    for feat_dict in features:
        location = FeatureLocation(
            feat_dict['start'],
            feat_dict['end'],
            strand=feat_dict.get('strand', 1)
        )
        
        feature = SeqFeature(
            location=location,
            type=feat_dict['type'],
            qualifiers=feat_dict.get('qualifiers', {})
        )
        
        # Add label if not in qualifiers
        if 'label' not in feature.qualifiers and 'label' in feat_dict:
            feature.qualifiers['label'] = feat_dict['label']
        
        record.features.append(feature)
    
    # Convert to GenBank format
    output = StringIO()
    SeqIO.write(record, output, "genbank")
    return output.getvalue()
