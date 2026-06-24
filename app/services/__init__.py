"""
Business logic services for the MoClo Library Tool.
"""

# Authentication
from .auth import AuthService

# Export services
from .export import (
    generate_fasta,
    export_cassette_fasta,
    generate_genbank,
    export_cassette_genbank,
    svg_to_png,
    generate_cassette_image,
    export_cassette_image,
    generate_part_image,
    export_part_image
)

# GenBank parsing
from .genbank_parser import (
    parse_genbank_file,
    extract_sequence,
    extract_features,
    extract_metadata,
    validate_genbank_content,
    get_resistance_markers,
    get_origins_of_replication,
    format_genbank_output,
    GenBankParseError
)

# Restriction site finding
from .restriction_sites import (
    find_moclo_sites,
    identify_cassette_slots,
    get_insertion_overhangs,
    validate_moclo_backbone,
    annotate_sites_in_sequence,
    MOCLO_ENZYMES
)

# Backbone compatibility
from .backbone_compatibility import (
    check_compatibility,
    find_compatible_backbones,
    find_compatible_cassettes,
    get_compatibility_score,
    get_insertion_position,
    explain_incompatibility,
    batch_check_compatibility
)

# Plasmid assembly
from .plasmid_assembly import (
    assemble_plasmid,
    validate_assembly,
    simulate_assembly,
    remove_restriction_sites,
    AssemblyError
)

# Circular map generation
from .circular_map import (
    generate_circular_map,
    generate_linear_map,
    FEATURE_COLORS
)

__all__ = [
    # Auth
    'AuthService',
    
    # Export
    'generate_fasta',
    'export_cassette_fasta',
    'generate_genbank',
    'export_cassette_genbank',
    'svg_to_png',
    'generate_cassette_image',
    'export_cassette_image',
    'generate_part_image',
    'export_part_image',
    
    # GenBank parsing
    'parse_genbank_file',
    'extract_sequence',
    'extract_features',
    'extract_metadata',
    'validate_genbank_content',
    'get_resistance_markers',
    'get_origins_of_replication',
    'format_genbank_output',
    'GenBankParseError',
    
    # Restriction sites
    'find_moclo_sites',
    'identify_cassette_slots',
    'get_insertion_overhangs',
    'validate_moclo_backbone',
    'annotate_sites_in_sequence',
    'MOCLO_ENZYMES',
    
    # Compatibility
    'check_compatibility',
    'find_compatible_backbones',
    'find_compatible_cassettes',
    'get_compatibility_score',
    'get_insertion_position',
    'explain_incompatibility',
    'batch_check_compatibility',
    
    # Assembly
    'assemble_plasmid',
    'validate_assembly',
    'simulate_assembly',
    'remove_restriction_sites',
    'AssemblyError',
    
    # Visualization
    'generate_circular_map',
    'generate_linear_map',
    'FEATURE_COLORS'
]
