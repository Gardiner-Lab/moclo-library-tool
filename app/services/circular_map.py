"""
Circular plasmid map generator.

This module provides functions to generate SVG circular maps
of plasmids showing features, size, and annotations.
"""

import math
from typing import List, Dict, Any, Tuple, Optional


# Feature type colors (for backbone features)
FEATURE_COLORS = {
    'CDS': '#FF6B6B',           # Red for coding sequences
    'promoter': '#4ECDC4',      # Teal for promoters
    'terminator': '#95E1D3',    # Light teal for terminators
    'rep_origin': '#FFE66D',    # Yellow for origins
    'origin': '#FFE66D',
    'misc_feature': '#C7CEEA',  # Light purple for misc
    'intron': '#B4A7D6',        # Purple for introns
    'resistance': '#FF8B94',    # Pink for resistance markers
    'RBS': '#A8E6CF',           # Light green for RBS
    'default': '#CCCCCC'        # Gray for unknown
}

# Part type colors (for cassette features - matches visualization.py)
PART_TYPE_COLORS = {
    'Coding': '#4A90E2',              # Blue
    'NonCodingPromoter': '#7ED321',   # Green
    'NonCodingTerminator': '#D0021B', # Red
    'NonCodingIntron': '#F5A623',     # Yellow/Orange
    'NonCodingOther': '#9B9B9B'       # Gray
}


def generate_circular_map(
    plasmid_name: str,
    sequence: str,
    features: List[Dict[str, Any]],
    width: int = 800,
    show_labels: bool = True,
    show_size_markers: bool = True,
    cassette_regions: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Generate an SVG circular plasmid map.
    
    Args:
        plasmid_name: Name of the plasmid
        sequence: DNA sequence
        features: List of feature dictionaries
        width: Width of the SVG in pixels
        show_labels: Whether to show feature labels
        show_size_markers: Whether to show size markers
        cassette_regions: List of cassette insertion regions with start, end, and name
        
    Returns:
        SVG string
    """
    size = len(sequence)
    height = width
    center_x = width / 2
    center_y = height / 2
    
    # Calculate radii
    outer_radius = min(width, height) * 0.35
    inner_radius = outer_radius * 0.7
    label_radius = outer_radius * 1.15
    cassette_radius = outer_radius * 1.25  # Radius for cassette highlights
    
    # Start SVG
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        '<defs>',
        '  <style>',
        '    .plasmid-label { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; }',
        '    .feature-label { font-family: Arial, sans-serif; font-size: 10px; }',
        '    .cassette-label { font-family: Arial, sans-serif; font-size: 11px; font-weight: bold; fill: #d63031; }',
        '    .size-label { font-family: Arial, sans-serif; font-size: 9px; fill: #666; }',
        '  </style>',
        '</defs>'
    ]
    
    # Draw plasmid name
    svg_parts.append(
        f'<text x="{center_x}" y="30" text-anchor="middle" class="plasmid-label">{plasmid_name}</text>'
    )
    
    # Draw size
    svg_parts.append(
        f'<text x="{center_x}" y="50" text-anchor="middle" class="size-label">{size} bp</text>'
    )
    
    # Draw backbone circle
    svg_parts.append(
        f'<circle cx="{center_x}" cy="{center_y}" r="{outer_radius}" '
        f'fill="none" stroke="#333" stroke-width="2"/>'
    )
    svg_parts.append(
        f'<circle cx="{center_x}" cy="{center_y}" r="{inner_radius}" '
        f'fill="none" stroke="#333" stroke-width="1"/>'
    )
    
    # Draw size markers
    if show_size_markers:
        svg_parts.extend(_draw_size_markers(
            center_x, center_y, outer_radius, size
        ))
    
    # Draw cassette regions (highlighted)
    if cassette_regions:
        svg_parts.extend(_draw_cassette_regions(
            cassette_regions, center_x, center_y, outer_radius, cassette_radius,
            size
        ))
    
    # Draw features
    if features:
        svg_parts.extend(_draw_features(
            features, center_x, center_y, inner_radius, outer_radius,
            size, show_labels, label_radius
        ))
    
    # Draw legend
    svg_parts.extend(_draw_legend(width, height, features))
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)


def _draw_cassette_regions(
    cassette_regions: List[Dict[str, Any]],
    center_x: float,
    center_y: float,
    outer_radius: float,
    cassette_radius: float,
    plasmid_size: int
) -> List[str]:
    """
    Draw highlighted cassette insertion regions.
    
    Args:
        cassette_regions: List of cassette region dicts with start, end, name
        center_x: Center X coordinate
        center_y: Center Y coordinate
        outer_radius: Outer circle radius
        cassette_radius: Radius for cassette highlights
        plasmid_size: Total plasmid size
        
    Returns:
        List of SVG elements
    """
    svg_parts = []
    
    for region in cassette_regions:
        start = region['start']
        end = region['end']
        name = region['name']
        
        # Calculate angles
        start_angle = (start / plasmid_size) * 2 * math.pi - math.pi / 2
        end_angle = (end / plasmid_size) * 2 * math.pi - math.pi / 2
        
        # Handle wrap-around
        if end < start:
            end_angle += 2 * math.pi
        
        # Draw highlight arc (thicker, colored)
        start_outer_x = center_x + cassette_radius * math.cos(start_angle)
        start_outer_y = center_y + cassette_radius * math.sin(start_angle)
        end_outer_x = center_x + cassette_radius * math.cos(end_angle)
        end_outer_y = center_y + cassette_radius * math.sin(end_angle)
        
        start_inner_x = center_x + outer_radius * math.cos(start_angle)
        start_inner_y = center_y + outer_radius * math.sin(start_angle)
        end_inner_x = center_x + outer_radius * math.cos(end_angle)
        end_inner_y = center_y + outer_radius * math.sin(end_angle)
        
        large_arc = 1 if (end_angle - start_angle) > math.pi else 0
        
        # Build highlight path
        path = f'M {start_outer_x},{start_outer_y} '
        path += f'A {cassette_radius},{cassette_radius} 0 {large_arc},1 {end_outer_x},{end_outer_y} '
        path += f'L {end_inner_x},{end_inner_y} '
        path += f'A {outer_radius},{outer_radius} 0 {large_arc},0 {start_inner_x},{start_inner_y} '
        path += 'Z'
        
        svg_parts.append(
            f'<path d="{path}" fill="#ff6b6b" stroke="#d63031" stroke-width="2" opacity="0.4"/>'
        )
        
        # Draw cassette label
        mid_angle = (start_angle + end_angle) / 2
        label_x = center_x + (cassette_radius + 15) * math.cos(mid_angle)
        label_y = center_y + (cassette_radius + 15) * math.sin(mid_angle)
        
        # Calculate rotation for text
        rotation = math.degrees(mid_angle) + 90
        if rotation > 90 and rotation < 270:
            rotation += 180
        
        # Draw label with full name (no truncation)
        svg_parts.append(
            f'<text x="{label_x}" y="{label_y}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'class="cassette-label" '
            f'transform="rotate({rotation} {label_x} {label_y})">'
            f'{name}</text>'
        )
        
        # Draw pointer lines from label to region
        pointer_start_x = center_x + cassette_radius * math.cos(mid_angle)
        pointer_start_y = center_y + cassette_radius * math.sin(mid_angle)
        pointer_end_x = center_x + (cassette_radius + 10) * math.cos(mid_angle)
        pointer_end_y = center_y + (cassette_radius + 10) * math.sin(mid_angle)
        
        svg_parts.append(
            f'<line x1="{pointer_start_x}" y1="{pointer_start_y}" '
            f'x2="{pointer_end_x}" y2="{pointer_end_y}" '
            f'stroke="#d63031" stroke-width="1.5"/>'
        )
    
    return svg_parts


def _draw_size_markers(
    center_x: float,
    center_y: float,
    radius: float,
    size: int,
    num_markers: int = 8
) -> List[str]:
    """
    Draw size markers around the circle.
    
    Args:
        center_x: Center X coordinate
        center_y: Center Y coordinate
        radius: Circle radius
        size: Plasmid size in bp
        num_markers: Number of markers to draw
        
    Returns:
        List of SVG elements
    """
    svg_parts = []
    marker_radius = radius * 1.05
    
    for i in range(num_markers):
        angle = (i / num_markers) * 2 * math.pi - math.pi / 2
        position = int((i / num_markers) * size)
        
        # Calculate marker position
        x = center_x + marker_radius * math.cos(angle)
        y = center_y + marker_radius * math.sin(angle)
        
        # Draw tick mark
        tick_start_x = center_x + radius * 0.98 * math.cos(angle)
        tick_start_y = center_y + radius * 0.98 * math.sin(angle)
        tick_end_x = center_x + radius * 1.02 * math.cos(angle)
        tick_end_y = center_y + radius * 1.02 * math.sin(angle)
        
        svg_parts.append(
            f'<line x1="{tick_start_x}" y1="{tick_start_y}" '
            f'x2="{tick_end_x}" y2="{tick_end_y}" '
            f'stroke="#666" stroke-width="1"/>'
        )
        
        # Draw label
        label_x = center_x + (radius * 1.08) * math.cos(angle)
        label_y = center_y + (radius * 1.08) * math.sin(angle)
        
        svg_parts.append(
            f'<text x="{label_x}" y="{label_y}" text-anchor="middle" '
            f'dominant-baseline="middle" class="size-label">{position}</text>'
        )
    
    return svg_parts


def _draw_features(
    features: List[Dict[str, Any]],
    center_x: float,
    center_y: float,
    inner_radius: float,
    outer_radius: float,
    plasmid_size: int,
    show_labels: bool,
    label_radius: float
) -> List[str]:
    """
    Draw features on the circular map.
    
    Args:
        features: List of feature dictionaries
        center_x: Center X coordinate
        center_y: Center Y coordinate
        inner_radius: Inner circle radius
        outer_radius: Outer circle radius
        plasmid_size: Total plasmid size
        show_labels: Whether to show labels
        label_radius: Radius for labels
        
    Returns:
        List of SVG elements
    """
    svg_parts = []
    
    # Sort features by start position
    sorted_features = sorted(features, key=lambda f: f['start'])
    
    for feature in sorted_features:
        start = feature['start']
        end = feature['end']
        feature_type = feature['type']
        label = feature.get('label', feature_type)
        strand = feature.get('strand', 1)
        
        # Get color for this feature type
        color = _get_feature_color(feature)
        
        # Calculate angles (0 degrees = top, clockwise)
        start_angle = (start / plasmid_size) * 2 * math.pi - math.pi / 2
        end_angle = (end / plasmid_size) * 2 * math.pi - math.pi / 2
        
        # Handle features that wrap around
        if end < start:
            end_angle += 2 * math.pi
        
        # Draw feature arc
        svg_parts.append(
            _draw_feature_arc(
                center_x, center_y, inner_radius, outer_radius,
                start_angle, end_angle, color, strand
            )
        )
        
        # Draw label if requested
        if show_labels and (end - start) > plasmid_size * 0.02:  # Only label if >2% of plasmid
            svg_parts.append(
                _draw_feature_label(
                    center_x, center_y, label_radius,
                    start_angle, end_angle, label
                )
            )
    
    return svg_parts


def _draw_feature_arc(
    center_x: float,
    center_y: float,
    inner_radius: float,
    outer_radius: float,
    start_angle: float,
    end_angle: float,
    color: str,
    strand: int
) -> str:
    """
    Draw a feature as an arc.
    
    Args:
        center_x: Center X coordinate
        center_y: Center Y coordinate
        inner_radius: Inner radius
        outer_radius: Outer radius
        start_angle: Start angle in radians
        end_angle: End angle in radians
        color: Fill color
        strand: 1 for forward, -1 for reverse
        
    Returns:
        SVG path element
    """
    # Calculate arc points
    start_outer_x = center_x + outer_radius * math.cos(start_angle)
    start_outer_y = center_y + outer_radius * math.sin(start_angle)
    end_outer_x = center_x + outer_radius * math.cos(end_angle)
    end_outer_y = center_y + outer_radius * math.sin(end_angle)
    
    start_inner_x = center_x + inner_radius * math.cos(start_angle)
    start_inner_y = center_y + inner_radius * math.sin(start_angle)
    end_inner_x = center_x + inner_radius * math.cos(end_angle)
    end_inner_y = center_y + inner_radius * math.sin(end_angle)
    
    # Determine if arc is large (>180 degrees)
    large_arc = 1 if (end_angle - start_angle) > math.pi else 0
    
    # Build path
    path = f'M {start_outer_x},{start_outer_y} '
    path += f'A {outer_radius},{outer_radius} 0 {large_arc},1 {end_outer_x},{end_outer_y} '
    path += f'L {end_inner_x},{end_inner_y} '
    path += f'A {inner_radius},{inner_radius} 0 {large_arc},0 {start_inner_x},{start_inner_y} '
    path += 'Z'
    
    # Add directional indicator for strand
    opacity = 0.8 if strand == 1 else 0.6
    
    return f'<path d="{path}" fill="{color}" stroke="#333" stroke-width="0.5" opacity="{opacity}"/>'


def _draw_feature_label(
    center_x: float,
    center_y: float,
    label_radius: float,
    start_angle: float,
    end_angle: float,
    label: str
) -> str:
    """
    Draw a feature label.
    
    Args:
        center_x: Center X coordinate
        center_y: Center Y coordinate
        label_radius: Radius for label placement
        start_angle: Feature start angle
        end_angle: Feature end angle
        label: Label text
        
    Returns:
        SVG text element
    """
    # Calculate middle angle
    mid_angle = (start_angle + end_angle) / 2
    
    # Calculate label position
    label_x = center_x + label_radius * math.cos(mid_angle)
    label_y = center_y + label_radius * math.sin(mid_angle)
    
    # Calculate rotation for text
    rotation = math.degrees(mid_angle) + 90
    
    # Adjust rotation to keep text readable
    if rotation > 90 and rotation < 270:
        rotation += 180
    
    # Don't truncate labels - show full name
    return (
        f'<text x="{label_x}" y="{label_y}" '
        f'text-anchor="middle" dominant-baseline="middle" '
        f'class="feature-label" '
        f'transform="rotate({rotation} {label_x} {label_y})">'
        f'{label}</text>'
    )


def _get_feature_color(feature: Dict[str, Any]) -> str:
    """
    Get the color for a feature based on its type.
    
    For cassette features, uses part type colors to match cassette visualization.
    For backbone features, uses standard feature type colors.
    
    Args:
        feature: Feature dictionary
        
    Returns:
        Hex color string
    """
    qualifiers = feature.get('qualifiers', {})
    
    # Check if this is a cassette feature
    if qualifiers.get('source') == 'cassette':
        # Use part type colors for cassette features
        part_type = qualifiers.get('part_type')
        if part_type and part_type in PART_TYPE_COLORS:
            return PART_TYPE_COLORS[part_type]
    
    # For backbone features, use standard feature type colors
    feature_type = feature['type'].lower()
    
    # Check for resistance markers
    label = feature.get('label', '').lower()
    qualifiers_str = str(qualifiers).lower()
    
    if 'resistance' in label or 'resistance' in qualifiers_str:
        return FEATURE_COLORS['resistance']
    
    # Check feature type
    for key, color in FEATURE_COLORS.items():
        if key.lower() in feature_type:
            return color
    
    return FEATURE_COLORS['default']


def _draw_legend(
    width: int,
    height: int,
    features: List[Dict[str, Any]]
) -> List[str]:
    """
    Draw a legend showing feature types.
    
    Args:
        width: SVG width
        height: SVG height
        features: List of features
        
    Returns:
        List of SVG elements
    """
    svg_parts = []
    
    # Get unique feature types
    feature_types = set()
    for feature in features:
        feature_types.add(feature['type'])
    
    if not feature_types:
        return svg_parts
    
    # Draw legend box
    legend_x = width - 150
    legend_y = height - 30 - (len(feature_types) * 20)
    legend_width = 140
    legend_height = 20 + (len(feature_types) * 20)
    
    svg_parts.append(
        f'<rect x="{legend_x}" y="{legend_y}" '
        f'width="{legend_width}" height="{legend_height}" '
        f'fill="white" stroke="#333" stroke-width="1" opacity="0.9"/>'
    )
    
    svg_parts.append(
        f'<text x="{legend_x + 10}" y="{legend_y + 15}" '
        f'class="feature-label" font-weight="bold">Features</text>'
    )
    
    # Draw legend items
    y_offset = legend_y + 30
    for feature_type in sorted(feature_types):
        color = FEATURE_COLORS.get(feature_type, FEATURE_COLORS['default'])
        
        # Draw color box
        svg_parts.append(
            f'<rect x="{legend_x + 10}" y="{y_offset}" '
            f'width="15" height="12" fill="{color}" stroke="#333" stroke-width="0.5"/>'
        )
        
        # Draw label
        svg_parts.append(
            f'<text x="{legend_x + 30}" y="{y_offset + 10}" '
            f'class="feature-label">{feature_type}</text>'
        )
        
        y_offset += 20
    
    return svg_parts


def generate_linear_map(
    plasmid_name: str,
    sequence: str,
    features: List[Dict[str, Any]],
    width: int = 800,
    height: int = 200
) -> str:
    """
    Generate an SVG linear plasmid map.
    
    Useful for showing plasmids in linear form.
    
    Args:
        plasmid_name: Name of the plasmid
        sequence: DNA sequence
        features: List of feature dictionaries
        width: Width of the SVG
        height: Height of the SVG
        
    Returns:
        SVG string
    """
    size = len(sequence)
    margin = 50
    map_width = width - 2 * margin
    map_height = 40
    map_y = height / 2 - map_height / 2
    
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        '<defs>',
        '  <style>',
        '    .plasmid-label { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; }',
        '    .feature-label { font-family: Arial, sans-serif; font-size: 10px; }',
        '  </style>',
        '</defs>'
    ]
    
    # Draw title
    svg_parts.append(
        f'<text x="{width/2}" y="30" text-anchor="middle" class="plasmid-label">'
        f'{plasmid_name} ({size} bp)</text>'
    )
    
    # Draw backbone line
    svg_parts.append(
        f'<rect x="{margin}" y="{map_y}" width="{map_width}" height="{map_height}" '
        f'fill="#f0f0f0" stroke="#333" stroke-width="2"/>'
    )
    
    # Draw features
    for feature in features:
        start = feature['start']
        end = feature['end']
        label = feature.get('label', feature['type'])
        
        # Calculate position
        feature_x = margin + (start / size) * map_width
        feature_width = ((end - start) / size) * map_width
        
        color = _get_feature_color(feature)
        
        # Draw feature box
        svg_parts.append(
            f'<rect x="{feature_x}" y="{map_y}" width="{feature_width}" height="{map_height}" '
            f'fill="{color}" stroke="#333" stroke-width="1" opacity="0.8"/>'
        )
        
        # Draw label if feature is large enough
        if feature_width > 30:
            label_x = feature_x + feature_width / 2
            label_y = map_y + map_height / 2
            
            if len(label) > 10:
                label = label[:8] + '...'
            
            svg_parts.append(
                f'<text x="{label_x}" y="{label_y}" text-anchor="middle" '
                f'dominant-baseline="middle" class="feature-label">{label}</text>'
            )
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)
