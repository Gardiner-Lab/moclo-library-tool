"""
Export service for generating FASTA and GenBank format files from cassettes.
"""

from typing import Optional, List
from datetime import datetime
from io import BytesIO
from app.models.cassette import Cassette
from app.models.part import Part
from app.services.visualization import generate_cassette_svg, generate_part_svg

# Lazy import for cairosvg to avoid import errors when Cairo library is not available
# This allows FASTA and GenBank exports to work even without Cairo installed
_cairosvg = None

def _get_cairosvg():
    """Lazy import of cairosvg module."""
    global _cairosvg
    if _cairosvg is None:
        try:
            import cairosvg as _cairo
            _cairosvg = _cairo
        except (ImportError, OSError) as e:
            raise ImportError(
                "cairosvg and Cairo library are required for image export. "
                "On Windows, you may need to install GTK+ runtime. "
                f"Original error: {str(e)}"
            )
    return _cairosvg


def generate_fasta(cassette: Cassette) -> str:
    """
    Generate FASTA format representation of a cassette.
    
    FASTA format consists of:
    - Header line starting with '>' followed by the sequence identifier/name
    - Sequence data on subsequent lines (typically wrapped at 60-80 characters)
    
    Args:
        cassette: Cassette instance to export
        
    Returns:
        String containing FASTA formatted data
        
    Example:
        >Test Cassette
        ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG
        ATCGATCGATCG
    """
    # FASTA header line with cassette name
    header = f">{cassette.name}"
    
    # Sequence body - wrap at 60 characters per line (standard FASTA format)
    sequence = cassette.assembled_sequence
    line_length = 60
    
    # Split sequence into lines of specified length
    sequence_lines = []
    for i in range(0, len(sequence), line_length):
        sequence_lines.append(sequence[i:i + line_length])
    
    # Combine header and sequence lines
    fasta_content = header + "\n" + "\n".join(sequence_lines)
    
    return fasta_content


def export_cassette_fasta(cassette_id: str) -> Optional[str]:
    """
    Export a cassette as FASTA format by cassette ID.
    
    Args:
        cassette_id: ID of the cassette to export
        
    Returns:
        FASTA formatted string if cassette exists, None otherwise
    """
    cassette = Cassette.get_by_id(cassette_id)
    
    if cassette is None:
        return None
    
    return generate_fasta(cassette)


def generate_genbank(cassette: Cassette) -> str:
    """
    Generate GenBank format representation of a cassette.
    
    GenBank format is a rich text format for sequence data that includes:
    - LOCUS line with sequence name, length, molecule type, and date
    - DEFINITION line with description
    - FEATURES section with annotations for each part
    - ORIGIN section with the actual sequence
    
    Args:
        cassette: Cassette instance to export
        
    Returns:
        String containing GenBank formatted data
        
    Example:
        LOCUS       Test_Cassette            20 bp    DNA     linear   01-JAN-2024
        DEFINITION  MoClo cassette assembly
        FEATURES             Location/Qualifiers
             misc_feature    1..12
                             /label="Promoter"
                             /part_type="NonCodingPromoter"
             misc_feature    13..20
                             /label="CDS"
                             /part_type="Coding"
        ORIGIN
                1 atcgatcgat cgcgatcgat
        //
    """
    # Get all parts for this cassette
    parts = []
    for part_id in cassette.part_ids:
        part = Part.get_by_id(part_id)
        if part:
            parts.append(part)
    
    # Generate LOCUS line
    # Format: LOCUS <name> <length> bp DNA linear <date>
    # Name should be max 16 characters, no spaces
    locus_name = cassette.name.replace(' ', '_')[:16]
    sequence_length = len(cassette.assembled_sequence)
    current_date = datetime.now().strftime('%d-%b-%Y').upper()
    
    locus_line = f"LOCUS       {locus_name:<16} {sequence_length:>6} bp    DNA     linear   {current_date}"
    
    # Generate DEFINITION line
    definition_line = "DEFINITION  MoClo cassette assembly"
    
    # Generate FEATURES section
    features_lines = ["FEATURES             Location/Qualifiers"]
    
    # Calculate positions for each part in the assembled sequence
    position = 1
    for i, part in enumerate(parts):
        # Calculate the length of this part in the assembled sequence
        if i == 0:
            # First part: full sequence
            part_length = len(part.sequence)
        else:
            # Subsequent parts: sequence minus 4-base overhang
            part_length = len(part.sequence) - 4
        
        start_pos = position
        end_pos = position + part_length - 1
        
        # Add feature annotation
        features_lines.append(f"     misc_feature    {start_pos}..{end_pos}")
        features_lines.append(f'                     /label="{part.name}"')
        features_lines.append(f'                     /part_type="{part.part_type}"')
        
        # Add optional description if available
        if part.description:
            features_lines.append(f'                     /note="{part.description}"')
        
        # Add lab source and contributor information
        features_lines.append(f'                     /lab_source="{part.lab_source}"')
        features_lines.append(f'                     /contributor="{part.contributor}"')
        
        # Update position for next part
        position = end_pos + 1
    
    # Generate ORIGIN section with sequence
    origin_lines = ["ORIGIN"]
    
    # Format sequence in GenBank style: 10 groups of 6 bases per line, with line numbers
    sequence = cassette.assembled_sequence.lower()
    line_number = 1
    
    for i in range(0, len(sequence), 60):
        # Get up to 60 bases for this line
        line_seq = sequence[i:i+60]
        
        # Split into groups of 10 bases (with spaces every 10 bases)
        formatted_seq = ''
        for j in range(0, len(line_seq), 10):
            formatted_seq += ' ' + line_seq[j:j+10]
        
        # Add line with number (right-aligned to 9 characters)
        origin_lines.append(f"{line_number:>9}{formatted_seq}")
        line_number += len(line_seq)
    
    # Combine all sections
    genbank_content = '\n'.join([
        locus_line,
        definition_line,
        '\n'.join(features_lines),
        '\n'.join(origin_lines),
        '//'
    ])
    
    return genbank_content


def export_cassette_genbank(cassette_id: str) -> Optional[str]:
    """
    Export a cassette as GenBank format by cassette ID.
    
    Args:
        cassette_id: ID of the cassette to export
        
    Returns:
        GenBank formatted string if cassette exists, None otherwise
    """
    cassette = Cassette.get_by_id(cassette_id)
    
    if cassette is None:
        return None
    
    return generate_genbank(cassette)


def svg_to_png(svg_content: str, output_width: Optional[int] = None) -> bytes:
    """
    Convert SVG content to PNG format.
    
    Uses cairosvg to render SVG as PNG with optional width scaling.
    
    Args:
        svg_content: SVG string to convert
        output_width: Optional width in pixels for the output PNG.
                     If provided, the image will be scaled proportionally.
        
    Returns:
        PNG image data as bytes
        
    Raises:
        ValueError: If SVG content is invalid or conversion fails
        ImportError: If cairosvg or Cairo library is not available
    """
    try:
        cairosvg = _get_cairosvg()
        # Convert SVG to PNG
        if output_width:
            png_data = cairosvg.svg2png(
                bytestring=svg_content.encode('utf-8'),
                output_width=output_width
            )
        else:
            png_data = cairosvg.svg2png(
                bytestring=svg_content.encode('utf-8')
            )
        
        return png_data
    except ImportError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to convert SVG to PNG: {str(e)}")


def generate_cassette_image(cassette: Cassette, width: int = 800) -> bytes:
    """
    Generate a PNG image representation of a cassette.
    
    The image includes:
    - All component parts with their colors and types
    - Part boundaries and labels
    - Overhang sequences at junctions
    - Compatibility indicators between parts
    - Chevrons for directional parts (Coding, Promoter)
    
    Args:
        cassette: Cassette instance to visualize
        width: Width of the output image in pixels (default: 800)
        
    Returns:
        PNG image data as bytes
        
    Raises:
        ValueError: If cassette has no parts or image generation fails
    """
    # Get all parts for this cassette
    parts = []
    for part_id in cassette.part_ids:
        part = Part.get_by_id(part_id)
        if part:
            parts.append(part)
    
    if not parts:
        raise ValueError("Cassette has no parts to visualize")
    
    # Generate SVG representation
    svg_content = generate_cassette_svg(parts, width=width)
    
    # Convert SVG to PNG
    png_data = svg_to_png(svg_content, output_width=width)
    
    return png_data


def export_cassette_image(cassette_id: str, width: int = 800) -> Optional[bytes]:
    """
    Export a cassette as a PNG image by cassette ID.
    
    Args:
        cassette_id: ID of the cassette to export
        width: Width of the output image in pixels (default: 800)
        
    Returns:
        PNG image data as bytes if cassette exists, None otherwise
    """
    cassette = Cassette.get_by_id(cassette_id)
    
    if cassette is None:
        return None
    
    return generate_cassette_image(cassette, width=width)


def generate_part_image(part: Part, width: int = 200) -> bytes:
    """
    Generate a PNG image representation of a single part.
    
    The image includes:
    - Colored rectangle based on part type
    - Part name label
    - Overhang sequences at both ends (5' and 3')
    - Chevrons for Coding and Promoter types
    
    Args:
        part: Part instance to visualize
        width: Width of the output image in pixels (default: 200)
        
    Returns:
        PNG image data as bytes
        
    Raises:
        ValueError: If image generation fails
    """
    # Generate SVG representation
    svg_content = generate_part_svg(part, width=width)
    
    # Convert SVG to PNG
    png_data = svg_to_png(svg_content, output_width=width)
    
    return png_data


def export_part_image(part_id: str, width: int = 200) -> Optional[bytes]:
    """
    Export a part as a PNG image by part ID.
    
    Args:
        part_id: ID of the part to export
        width: Width of the output image in pixels (default: 200)
        
    Returns:
        PNG image data as bytes if part exists, None otherwise
    """
    part = Part.get_by_id(part_id)
    
    if part is None:
        return None
    
    return generate_part_image(part, width=width)



def generate_part_genbank(part: Part) -> str:
    """
    Generate GenBank format representation of a part.
    
    Args:
        part: Part instance to export
        
    Returns:
        String containing GenBank formatted data
    """
    from app.models.part import Part
    
    # Generate LOCUS line
    locus_name = part.name.replace(' ', '_')[:16]
    sequence_length = len(part.sequence)
    current_date = datetime.now().strftime('%d-%b-%Y').upper()
    
    locus_line = f"LOCUS       {locus_name:<16} {sequence_length:>6} bp    DNA     linear   {current_date}"
    
    # Generate DEFINITION line
    definition_line = f"DEFINITION  {part.part_type} part - {part.name}"
    
    # Generate FEATURES section
    features_lines = ["FEATURES             Location/Qualifiers"]
    
    # Map part type to GenBank feature type
    feature_type_map = {
        'Coding': 'CDS',
        'NonCodingPromoter': 'promoter',
        'NonCodingTerminator': 'terminator',
        'NonCodingIntron': 'intron',
        'NonCodingOther': 'misc_feature'
    }
    feature_type = feature_type_map.get(part.part_type, 'misc_feature')
    
    # Add main feature for the part sequence
    features_lines.append(f"     {feature_type:<16}1..{sequence_length}")
    features_lines.append(f'                     /label="{part.name}"')
    features_lines.append(f'                     /part_type="{part.part_type}"')
    
    if part.description:
        features_lines.append(f'                     /note="{part.description}"')
    
    features_lines.append(f'                     /lab_source="{part.lab_source}"')
    features_lines.append(f'                     /contributor="{part.contributor}"')
    features_lines.append(f'                     /overhang_5prime="{part.overhang_5prime}"')
    features_lines.append(f'                     /overhang_3prime="{part.overhang_3prime}"')
    
    # Add optional metadata
    if hasattr(part, 'plasmid_id') and part.plasmid_id:
        features_lines.append(f'                     /plasmid_id="{part.plasmid_id}"')
    if hasattr(part, 'donor_organism') and part.donor_organism:
        features_lines.append(f'                     /organism="{part.donor_organism}"')
    if hasattr(part, 'comments') and part.comments:
        features_lines.append(f'                     /comment="{part.comments}"')
    
    # Generate ORIGIN section with sequence
    origin_lines = ["ORIGIN"]
    
    # Format sequence in GenBank style
    sequence = part.sequence.lower()
    line_number = 1
    
    for i in range(0, len(sequence), 60):
        line_seq = sequence[i:i+60]
        formatted_seq = ''
        for j in range(0, len(line_seq), 10):
            formatted_seq += ' ' + line_seq[j:j+10]
        origin_lines.append(f"{line_number:>9}{formatted_seq}")
        line_number += len(line_seq)
    
    # Combine all sections
    genbank_content = '\n'.join([
        locus_line,
        definition_line,
        '\n'.join(features_lines),
        '\n'.join(origin_lines),
        '//'
    ])
    
    return genbank_content


def export_part_genbank(part_id: str) -> Optional[str]:
    """
    Export a part as GenBank format by part ID.
    
    Args:
        part_id: ID of the part to export
        
    Returns:
        GenBank formatted string if part exists, None otherwise
    """
    from app.models.part import Part
    part = Part.get_by_id(part_id)
    
    if part is None:
        return None
    
    return generate_part_genbank(part)


def generate_backbone_genbank(backbone) -> str:
    """
    Generate GenBank format representation of a backbone.
    
    Args:
        backbone: Backbone instance to export
        
    Returns:
        String containing GenBank formatted data
    """
    # Generate LOCUS line
    locus_name = backbone.name.replace(' ', '_')[:16]
    sequence_length = len(backbone.sequence)
    current_date = datetime.now().strftime('%d-%b-%Y').upper()
    
    # Backbones are typically circular
    topology = 'circular'
    locus_line = f"LOCUS       {locus_name:<16} {sequence_length:>6} bp    DNA     {topology:<8} {current_date}"
    
    # Generate DEFINITION line
    definition_line = f"DEFINITION  MoClo backbone - {backbone.name}"
    if backbone.description:
        definition_line += f" - {backbone.description}"
    
    # Generate FEATURES section
    features_lines = ["FEATURES             Location/Qualifiers"]
    
    # Add restriction sites as features
    if backbone.restriction_sites:
        from app.services.restriction_sites import identify_cassette_slots
        
        # Check if sites are already in slot format
        if 'slot_number' in backbone.restriction_sites[0]:
            slots = backbone.restriction_sites
        else:
            slots = identify_cassette_slots(backbone.restriction_sites)
        
        for slot in slots:
            slot_num = slot.get('slot_number', 1)
            site_5prime = slot.get('site_5prime', {})
            site_3prime = slot.get('site_3prime', {})
            
            # Add 5' site
            if site_5prime:
                pos = site_5prime.get('position', 0)
                enzyme = site_5prime.get('enzyme', 'BsaI')
                features_lines.append(f"     misc_feature    {pos}..{pos+6}")
                features_lines.append(f'                     /label="{enzyme}_site_5prime_slot{slot_num}"')
                features_lines.append(f'                     /enzyme="{enzyme}"')
                features_lines.append(f'                     /slot="{slot_num}"')
            
            # Add 3' site
            if site_3prime:
                pos = site_3prime.get('position', 0)
                enzyme = site_3prime.get('enzyme', 'BsaI')
                features_lines.append(f"     misc_feature    {pos}..{pos+6}")
                features_lines.append(f'                     /label="{enzyme}_site_3prime_slot{slot_num}"')
                features_lines.append(f'                     /enzyme="{enzyme}"')
                features_lines.append(f'                     /slot="{slot_num}"')
            
            # Add insertion slot region
            if 'insertion_start' in slot and 'insertion_end' in slot:
                start = slot['insertion_start']
                end = slot['insertion_end']
                features_lines.append(f"     misc_feature    {start}..{end}")
                features_lines.append(f'                     /label="cassette_slot_{slot_num}"')
                features_lines.append(f'                     /slot_number="{slot_num}"')
                overhang_5 = slot.get('expected_overhang_5prime', 'NNNN')
                overhang_3 = slot.get('expected_overhang_3prime', 'NNNN')
                features_lines.append(f'                     /expected_overhangs="{overhang_5}...{overhang_3}"')
    
    # Add features from genbank_data if available
    if hasattr(backbone, 'features') and backbone.features:
        for feature in backbone.features:
            feature_type = feature.get('type', 'misc_feature')
            start = feature.get('start', 1)
            end = feature.get('end', sequence_length)
            label = feature.get('label', 'feature')
            
            features_lines.append(f"     {feature_type:<16}{start}..{end}")
            features_lines.append(f'                     /label="{label}"')
            
            # Add qualifiers
            qualifiers = feature.get('qualifiers', {})
            for key, value in qualifiers.items():
                if key not in ['label']:
                    features_lines.append(f'                     /{key}="{value}"')
    
    # Add metadata as features
    if hasattr(backbone, 'antibiotic') and backbone.antibiotic:
        features_lines.append(f"     misc_feature    1..{sequence_length}")
        features_lines.append(f'                     /label="antibiotic_resistance"')
        features_lines.append(f'                     /antibiotic="{backbone.antibiotic}"')
    
    # Generate ORIGIN section with sequence
    origin_lines = ["ORIGIN"]
    
    sequence = backbone.sequence.lower()
    line_number = 1
    
    for i in range(0, len(sequence), 60):
        line_seq = sequence[i:i+60]
        formatted_seq = ''
        for j in range(0, len(line_seq), 10):
            formatted_seq += ' ' + line_seq[j:j+10]
        origin_lines.append(f"{line_number:>9}{formatted_seq}")
        line_number += len(line_seq)
    
    # Combine all sections
    genbank_content = '\n'.join([
        locus_line,
        definition_line,
        '\n'.join(features_lines),
        '\n'.join(origin_lines),
        '//'
    ])
    
    return genbank_content


def export_backbone_genbank(backbone_id: str) -> Optional[str]:
    """
    Export a backbone as GenBank format by backbone ID.
    
    Args:
        backbone_id: ID of the backbone to export
        
    Returns:
        GenBank formatted string if backbone exists, None otherwise
    """
    from app.models.backbone import Backbone
    backbone = Backbone.get_by_id(backbone_id)
    
    if backbone is None:
        return None
    
    return generate_backbone_genbank(backbone)


def create_composite_plasmid_image(
    plasmid_svg: str,
    cassettes: List[Cassette],
    plasmid_name: str,
    output_width: int = 800
) -> bytes:
    """
    Create a composite image with plasmid circular map and cassette visualizations.
    
    The composite image includes:
    - Plasmid circular map at the top
    - Cassette visualizations below in a grid
    - Title and labels
    
    Args:
        plasmid_svg: SVG content of the plasmid circular map
        cassettes: List of Cassette objects to include
        plasmid_name: Name of the plasmid for the title
        output_width: Width of the output image in pixels
        
    Returns:
        PNG image data as bytes
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Convert plasmid SVG to PNG
        plasmid_png = svg_to_png(plasmid_svg, output_width=output_width)
        plasmid_img = Image.open(io.BytesIO(plasmid_png))
        
        # Generate cassette images
        cassette_images = []
        cassette_height = 100
        cassette_width = min(250, output_width // max(len(cassettes), 1) - 20)
        
        for cassette in cassettes:
            try:
                # Generate cassette SVG
                cassette_svg = generate_cassette_svg(
                    [Part.get_by_id(pid) for pid in cassette.part_ids if Part.get_by_id(pid)],
                    width=cassette_width
                )
                cassette_png = svg_to_png(cassette_svg, output_width=cassette_width)
                cassette_img = Image.open(io.BytesIO(cassette_png))
                
                # Resize to standard height while maintaining aspect ratio
                aspect_ratio = cassette_img.width / cassette_img.height
                new_height = cassette_height
                new_width = int(new_height * aspect_ratio)
                cassette_img = cassette_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                cassette_images.append((cassette_img, cassette.name))
            except Exception as e:
                print(f"Failed to generate image for cassette {cassette.name}: {e}")
                continue
        
        # Calculate composite image dimensions
        title_height = 60
        cassette_section_height = 0
        if cassette_images:
            # Calculate rows needed for cassettes
            cassettes_per_row = max(1, output_width // (cassette_width + 20))
            num_rows = (len(cassette_images) + cassettes_per_row - 1) // cassettes_per_row
            cassette_section_height = num_rows * (cassette_height + 60) + 40  # Extra space for labels
        
        total_height = title_height + plasmid_img.height + cassette_section_height + 40
        
        # Create composite image
        composite = Image.new('RGB', (output_width, total_height), 'white')
        draw = ImageDraw.Draw(composite)
        
        # Try to load a font, fall back to default if not available
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            title_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
        
        # Draw title
        title_text = f"Plasmid: {plasmid_name}"
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((output_width - title_width) // 2, 20), title_text, fill='black', font=title_font)
        
        # Paste plasmid circular map
        plasmid_y = title_height
        plasmid_x = (output_width - plasmid_img.width) // 2
        composite.paste(plasmid_img, (plasmid_x, plasmid_y))
        
        # Draw cassettes section
        if cassette_images:
            cassettes_y = plasmid_y + plasmid_img.height + 40
            
            # Draw section title
            cassettes_title = "Cassettes:"
            draw.text((20, cassettes_y - 30), cassettes_title, fill='black', font=title_font)
            
            # Arrange cassettes in a grid
            cassettes_per_row = max(1, output_width // (cassette_width + 20))
            x_offset = 20
            y_offset = cassettes_y
            
            for idx, (cassette_img, cassette_name) in enumerate(cassette_images):
                if idx > 0 and idx % cassettes_per_row == 0:
                    x_offset = 20
                    y_offset += cassette_height + 60
                
                # Paste cassette image
                composite.paste(cassette_img, (x_offset, y_offset))
                
                # Draw cassette name below image
                name_bbox = draw.textbbox((0, 0), cassette_name, font=label_font)
                name_width = name_bbox[2] - name_bbox[0]
                name_x = x_offset + (cassette_img.width - name_width) // 2
                name_y = y_offset + cassette_height + 5
                
                # Truncate name if too long
                if name_width > cassette_img.width:
                    max_chars = int(len(cassette_name) * cassette_img.width / name_width)
                    truncated_name = cassette_name[:max_chars-3] + "..."
                    draw.text((x_offset, name_y), truncated_name, fill='black', font=label_font)
                else:
                    draw.text((name_x, name_y), cassette_name, fill='black', font=label_font)
                
                x_offset += cassette_img.width + 20
        
        # Convert to PNG bytes
        output = io.BytesIO()
        composite.save(output, format='PNG')
        return output.getvalue()
        
    except ImportError as e:
        # Fall back to just the plasmid map if PIL is not available
        print(f"PIL not available, falling back to plasmid map only: {e}")
        return svg_to_png(plasmid_svg, output_width=output_width)
    except Exception as e:
        print(f"Error creating composite image: {e}")
        # Fall back to just the plasmid map
        return svg_to_png(plasmid_svg, output_width=output_width)
