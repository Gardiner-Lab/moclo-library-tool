"""
Visualization service for generating SVG representations of parts and cassettes.
"""

from typing import List, Dict, Any
from app.models.part import Part
import html


# Color scheme for part types
PART_COLORS = {
    'Coding': '#4A90E2',  # Blue
    'NonCodingPromoter': '#7ED321',  # Green
    'NonCodingTerminator': '#D0021B',  # Red
    'NonCodingIntron': '#F5A623',  # Yellow
    'NonCodingOther': '#9B9B9B'  # Gray
}

# Part types that should display chevrons
CHEVRON_TYPES = {'Coding', 'NonCodingPromoter'}


def escape_xml(text: str) -> str:
    """Escape special XML characters in text."""
    return html.escape(text)


def generate_part_svg(part: Part, width: int = 200, height: int = 80) -> str:
    """
    Generate an SVG representation of a single part.
    
    The visualization includes:
    - Colored rectangle based on part type
    - Chevrons for Coding and Promoter types
    - Overhang labels at both ends
    
    Args:
        part: Part instance to visualize
        width: Width of the SVG in pixels (default: 200)
        height: Height of the SVG in pixels (default: 80)
        
    Returns:
        SVG string representation of the part
    """
    # Get color for this part type
    color = PART_COLORS.get(part.part_type, PART_COLORS['NonCodingOther'])
    
    # Calculate dimensions
    padding = 10
    label_height = 15
    rect_height = height - (2 * label_height) - (2 * padding)
    rect_y = label_height + padding
    
    # Start building SVG
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'  <!-- Part: {part.name} ({part.part_type}) -->'
    ]
    
    # Add 5' overhang label (top)
    svg_parts.append(
        f'  <text x="{width // 2}" y="{label_height}" '
        f'text-anchor="middle" font-family="monospace" font-size="12" fill="#333">'
        f"5'-{part.overhang_5prime}</text>"
    )
    
    # Add main rectangle for the part
    svg_parts.append(
        f'  <rect x="{padding}" y="{rect_y}" '
        f'width="{width - 2 * padding}" height="{rect_height}" '
        f'fill="{color}" stroke="#333" stroke-width="2" rx="3"/>'
    )
    
    # Add chevrons for Coding and Promoter types
    if part.part_type in CHEVRON_TYPES:
        chevrons = _generate_chevrons(
            padding, rect_y, width - 2 * padding, rect_height, color
        )
        svg_parts.extend(chevrons)
    
    # Add part name in the center with adaptive sizing
    part_name = part.name
    text_x = width // 2
    text_y = rect_y + (rect_height // 2) + 5
    available_width = width - 2 * padding
    
    # Calculate appropriate font size based on name length and available width
    # Rough estimate: each character needs about 8 pixels at font-size 14
    chars_per_line = int(available_width / 8)
    
    if len(part_name) <= chars_per_line:
        # Name fits in one line at normal size
        font_size = 14
        svg_parts.append(
            f'  <text x="{text_x}" y="{text_y}" '
            f'text-anchor="middle" font-family="Arial, sans-serif" '
            f'font-size="{font_size}" font-weight="bold" fill="white">'
            f'{escape_xml(part_name)}</text>'
        )
    else:
        # Name is too long - try smaller font first
        font_size = max(9, int(14 * chars_per_line / len(part_name)))
        chars_per_line_small = int(available_width / (font_size * 0.6))
        
        if len(part_name) <= chars_per_line_small:
            # Fits with smaller font
            svg_parts.append(
                f'  <text x="{text_x}" y="{text_y}" '
                f'text-anchor="middle" font-family="Arial, sans-serif" '
                f'font-size="{font_size}" font-weight="bold" fill="white">'
                f'{escape_xml(part_name)}</text>'
            )
        else:
            # Need to wrap text into multiple lines
            words = part_name.split()
            lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                word_length = len(word)
                if current_length + word_length + len(current_line) <= chars_per_line_small:
                    current_line.append(word)
                    current_length += word_length
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = word_length
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Allow up to 2 lines for part visualization
            if len(lines) > 2:
                lines = lines[:2]
                # Show ellipsis only if really necessary
                if len(lines[1]) > chars_per_line_small:
                    lines[1] = lines[1][:chars_per_line_small-3] + '...'
            
            # Draw multi-line text
            line_height = font_size + 2
            start_y = text_y - ((len(lines) - 1) * line_height / 2)
            
            for line_idx, line in enumerate(lines):
                line_y = start_y + (line_idx * line_height)
                svg_parts.append(
                    f'  <text x="{text_x}" y="{line_y}" '
                    f'text-anchor="middle" font-family="Arial, sans-serif" '
                    f'font-size="{font_size}" font-weight="bold" fill="white">'
                    f'{escape_xml(line)}</text>'
                )
    
    # Add 3' overhang label (bottom)
    svg_parts.append(
        f'  <text x="{width // 2}" y="{height - 5}" '
        f'text-anchor="middle" font-family="monospace" font-size="12" fill="#333">'
        f"{part.overhang_3prime}-3'</text>"
    )
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)


def _generate_chevrons(
    x: float, y: float, width: float, height: float, base_color: str
) -> List[str]:
    """
    Generate chevron patterns for directional indication.
    
    Chevrons are right-pointing arrows (>>>) that indicate the 5' to 3' direction.
    They are rendered as darker overlays on the part rectangle.
    
    Args:
        x: X position of the rectangle
        y: Y position of the rectangle
        width: Width of the rectangle
        height: Height of the rectangle
        base_color: Base color of the part (used to create darker chevrons)
        
    Returns:
        List of SVG path strings for chevrons
    """
    chevrons = []
    
    # Create 3-4 chevrons evenly spaced across the part
    num_chevrons = 3
    chevron_width = 15
    chevron_spacing = (width - (num_chevrons * chevron_width)) / (num_chevrons + 1)
    
    # Darken the base color for chevrons
    chevron_color = _darken_color(base_color, 0.3)
    
    for i in range(num_chevrons):
        # Calculate chevron position
        chevron_x = x + chevron_spacing + (i * (chevron_width + chevron_spacing))
        chevron_y = y + (height / 2)
        
        # Create right-pointing chevron (>)
        # Path: start at left, go to middle-top, to right-middle, to middle-bottom, back to left
        path = (
            f'M {chevron_x},{chevron_y} '
            f'L {chevron_x + chevron_width * 0.4},{chevron_y - height * 0.25} '
            f'L {chevron_x + chevron_width},{chevron_y} '
            f'L {chevron_x + chevron_width * 0.4},{chevron_y + height * 0.25} '
            f'Z'
        )
        
        chevrons.append(
            f'  <path d="{path}" fill="{chevron_color}" opacity="0.6"/>'
        )
    
    return chevrons


def _darken_color(hex_color: str, factor: float = 0.3) -> str:
    """
    Darken a hex color by a given factor.
    
    Args:
        hex_color: Hex color string (e.g., '#4A90E2')
        factor: Darkening factor (0.0 = no change, 1.0 = black)
        
    Returns:
        Darkened hex color string
    """
    # Remove '#' if present
    hex_color = hex_color.lstrip('#')
    
    # Convert to RGB
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    # Darken each component
    r = int(r * (1 - factor))
    g = int(g * (1 - factor))
    b = int(b * (1 - factor))
    
    # Convert back to hex
    return f'#{r:02x}{g:02x}{b:02x}'


def generate_cassette_svg(
    parts: List[Part], width: int = 800, height: int = 120
) -> str:
    """
    Generate an SVG representation of a cassette (multiple connected parts).
    
    The visualization shows:
    - All parts in order with their colors
    - Overhang scars as visible elements between parts
    - Overhang labels at junctions between parts
    - Compatibility indicators (green checkmark for compatible, red X for incompatible)
    - Part names within each part (full names, not truncated)
    - Chevrons for Coding and Promoter types
    
    Args:
        parts: Ordered list of Part instances in the cassette
        width: Total width of the SVG in pixels (default: 800)
        height: Height of the SVG in pixels (default: 120)
        
    Returns:
        SVG string representation of the cassette
    """
    if not parts:
        return '<svg width="100" height="50" xmlns="http://www.w3.org/2000/svg"><text x="10" y="25">Empty cassette</text></svg>'
    
    # Calculate dimensions
    padding = 20
    label_height = 20
    scar_width = 30  # Wider to accommodate horizontal text (4 letters)
    rect_height = height - (2 * label_height) - (2 * padding)
    rect_y = label_height + padding
    
    # Calculate part widths (distribute evenly, accounting for scars)
    num_scars = len(parts) - 1
    total_scar_width = num_scars * scar_width
    available_width = width - (2 * padding) - total_scar_width
    part_width = available_width / len(parts)
    
    # Start building SVG
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'  <!-- Cassette with {len(parts)} parts and {num_scars} overhang scars -->'
    ]
    
    # Draw each part and scar
    current_x = padding
    
    for i, part in enumerate(parts):
        part_x = current_x
        color = PART_COLORS.get(part.part_type, PART_COLORS['NonCodingOther'])
        
        # Draw part rectangle
        svg_parts.append(
            f'  <rect x="{part_x}" y="{rect_y}" '
            f'width="{part_width}" height="{rect_height}" '
            f'fill="{color}" stroke="#333" stroke-width="2" rx="3"/>'
        )
        
        # Add chevrons for Coding and Promoter types
        if part.part_type in CHEVRON_TYPES:
            chevrons = _generate_chevrons(
                part_x, rect_y, part_width, rect_height, color
            )
            svg_parts.extend(chevrons)
        
        # Add part name - always show full name with adaptive sizing
        part_name = part.name
        text_x = part_x + (part_width / 2)
        text_y = rect_y + (rect_height / 2) + 5
        
        # Calculate appropriate font size based on name length and part width
        # Rough estimate: each character needs about 7 pixels at font-size 12
        chars_per_line = int(part_width / 7)
        
        if len(part_name) <= chars_per_line:
            # Name fits in one line at normal size
            font_size = 12
            svg_parts.append(
                f'  <text x="{text_x}" y="{text_y}" '
                f'text-anchor="middle" font-family="Arial, sans-serif" '
                f'font-size="{font_size}" font-weight="bold" fill="white">'
                f'{escape_xml(part_name)}</text>'
            )
        else:
            # Name is too long - try smaller font first
            font_size = max(8, int(12 * chars_per_line / len(part_name)))
            chars_per_line_small = int(part_width / (font_size * 0.6))
            
            if len(part_name) <= chars_per_line_small:
                # Fits with smaller font
                svg_parts.append(
                    f'  <text x="{text_x}" y="{text_y}" '
                    f'text-anchor="middle" font-family="Arial, sans-serif" '
                    f'font-size="{font_size}" font-weight="bold" fill="white">'
                    f'{escape_xml(part_name)}</text>'
                )
            else:
                # Need to wrap text into multiple lines
                words = part_name.split()
                lines = []
                current_line = []
                current_length = 0
                
                for word in words:
                    word_length = len(word)
                    if current_length + word_length + len(current_line) <= chars_per_line_small:
                        current_line.append(word)
                        current_length += word_length
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                        current_length = word_length
                
                if current_line:
                    lines.append(' '.join(current_line))
                
                # Allow up to 3 lines for very long names
                if len(lines) > 3:
                    lines = lines[:3]
                    # Show ellipsis only if really necessary
                    if len(lines[2]) > chars_per_line_small:
                        lines[2] = lines[2][:chars_per_line_small-3] + '...'
                
                # Draw multi-line text
                line_height = font_size + 2
                start_y = text_y - ((len(lines) - 1) * line_height / 2)
                
                for line_idx, line in enumerate(lines):
                    line_y = start_y + (line_idx * line_height)
                    svg_parts.append(
                        f'  <text x="{text_x}" y="{line_y}" '
                        f'text-anchor="middle" font-family="Arial, sans-serif" '
                        f'font-size="{font_size}" font-weight="bold" fill="white">'
                        f'{escape_xml(line)}</text>'
                    )
        
        # Add overhang labels
        if i == 0:
            # First part: show 5' overhang at the start
            svg_parts.append(
                f'  <text x="{part_x + part_width / 2}" y="{label_height}" '
                f'text-anchor="middle" font-family="monospace" font-size="11" fill="#333">'
                f"5'-{part.overhang_5prime}</text>"
            )
        
        # Move to next position (after this part)
        current_x += part_width
        
        # Draw overhang scar between parts
        if i < len(parts) - 1:
            next_part = parts[i + 1]
            scar_x = current_x
            
            # Check compatibility: current part's 3' overhang should match next part's 5' overhang
            is_compatible = (part.overhang_3prime == next_part.overhang_5prime)
            
            # Draw scar rectangle
            scar_color = '#FFD700' if is_compatible else '#FF6B6B'  # Gold for compatible, red for incompatible
            svg_parts.append(
                f'  <!-- Overhang scar: {part.overhang_3prime} -->'
            )
            svg_parts.append(
                f'  <rect x="{scar_x}" y="{rect_y}" '
                f'width="{scar_width}" height="{rect_height}" '
                f'fill="{scar_color}" stroke="#333" stroke-width="1.5"/>'
            )
            
            # Add diagonal stripes pattern to scar for visual distinction
            stripe_spacing = 4
            for stripe_offset in range(0, int(rect_height), stripe_spacing * 2):
                svg_parts.append(
                    f'  <line x1="{scar_x}" y1="{rect_y + stripe_offset}" '
                    f'x2="{scar_x + scar_width}" y2="{rect_y + stripe_offset + scar_width}" '
                    f'stroke="#333" stroke-width="0.5" opacity="0.3"/>'
                )
            
            # Display overhang sequence horizontally on the scar
            scar_center_x = scar_x + (scar_width / 2)
            scar_center_y = rect_y + (rect_height / 2) + 4
            
            svg_parts.append(
                f'  <text x="{scar_center_x}" y="{scar_center_y}" '
                f'text-anchor="middle" font-family="monospace" font-size="10" '
                f'fill="#000" font-weight="bold">'
                f'{part.overhang_3prime}</text>'
            )
            
            # Add compatibility indicator below
            indicator_y = rect_y + rect_height + 10
            if is_compatible:
                # Green checkmark for compatible parts
                svg_parts.append(
                    f'  <text x="{scar_center_x}" y="{indicator_y}" '
                    f'text-anchor="middle" font-size="14" fill="#22C55E">✓</text>'
                )
            else:
                # Red X for incompatible parts
                svg_parts.append(
                    f'  <text x="{scar_center_x}" y="{indicator_y}" '
                    f'text-anchor="middle" font-size="14" fill="#EF4444">✗</text>'
                )
                # Also add warning text
                svg_parts.append(
                    f'  <text x="{scar_center_x}" y="{indicator_y + 10}" '
                    f'text-anchor="middle" font-size="7" fill="#EF4444">'
                    f'Incompatible</text>'
                )
            
            # Move past the scar
            current_x += scar_width
        
        # Last part: show 3' overhang at the end
        if i == len(parts) - 1:
            svg_parts.append(
                f'  <text x="{part_x + part_width / 2}" y="{height - 5}" '
                f'text-anchor="middle" font-family="monospace" font-size="11" fill="#333">'
                f"{part.overhang_3prime}-3'</text>"
            )
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)
