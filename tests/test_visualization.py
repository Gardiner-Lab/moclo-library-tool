"""
Unit tests for the visualization service.
"""

import pytest
from app.models.part import Part
from app.services.visualization import (
    generate_part_svg,
    generate_cassette_svg,
    PART_COLORS,
    CHEVRON_TYPES,
    _darken_color
)


class TestPartSVGGeneration:
    """Tests for individual part SVG generation."""
    
    def test_generate_coding_part_svg(self):
        """Test SVG generation for a Coding part."""
        part = Part(
            id='test-1',
            name='GFP',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor='testuser'
        )
        
        svg = generate_part_svg(part)
        
        # Check that SVG is generated
        assert svg.startswith('<svg')
        assert svg.endswith('</svg>')
        
        # Check for part name
        assert 'GFP' in svg
        
        # Check for overhangs
        assert "5'-AATG" in svg
        assert "GCTT-3'" in svg
        
        # Check for correct color (blue for Coding)
        assert PART_COLORS['Coding'] in svg
        
        # Check for chevrons (Coding should have chevrons)
        assert '<path' in svg  # Chevrons are drawn as paths
    
    def test_generate_promoter_part_svg(self):
        """Test SVG generation for a NonCodingPromoter part."""
        part = Part(
            id='test-2',
            name='pLac',
            part_type='NonCodingPromoter',
            sequence='ATCGATCGATCG',
            overhang_5prime='GGAG',
            overhang_3prime='AATG',
            lab_source='Test Lab',
            contributor='testuser'
        )
        
        svg = generate_part_svg(part)
        
        # Check for correct color (green for Promoter)
        assert PART_COLORS['NonCodingPromoter'] in svg
        
        # Check for chevrons (Promoter should have chevrons)
        assert '<path' in svg
    
    def test_generate_terminator_part_svg(self):
        """Test SVG generation for a NonCodingTerminator part."""
        part = Part(
            id='test-3',
            name='T7term',
            part_type='NonCodingTerminator',
            sequence='ATCGATCGATCG',
            overhang_5prime='GCTT',
            overhang_3prime='CGCT',
            lab_source='Test Lab',
            contributor='testuser'
        )
        
        svg = generate_part_svg(part)
        
        # Check for correct color (red for Terminator)
        assert PART_COLORS['NonCodingTerminator'] in svg
        
        # Terminators should NOT have chevrons
        # Count path elements - should be minimal (no chevron paths)
        path_count = svg.count('<path')
        assert path_count == 0, "Terminator should not have chevrons"
    
    def test_generate_intron_part_svg(self):
        """Test SVG generation for a NonCodingIntron part."""
        part = Part(
            id='test-4',
            name='Intron1',
            part_type='NonCodingIntron',
            sequence='ATCGATCGATCG',
            overhang_5prime='TTCG',
            overhang_3prime='AATT',
            lab_source='Test Lab',
            contributor='testuser'
        )
        
        svg = generate_part_svg(part)
        
        # Check for correct color (yellow for Intron)
        assert PART_COLORS['NonCodingIntron'] in svg
        
        # Introns should NOT have chevrons
        path_count = svg.count('<path')
        assert path_count == 0, "Intron should not have chevrons"
    
    def test_generate_other_part_svg(self):
        """Test SVG generation for a NonCodingOther part."""
        part = Part(
            id='test-5',
            name='Spacer',
            part_type='NonCodingOther',
            sequence='ATCGATCGATCG',
            overhang_5prime='CCGG',
            overhang_3prime='TTAA',
            lab_source='Test Lab',
            contributor='testuser'
        )
        
        svg = generate_part_svg(part)
        
        # Check for correct color (gray for Other)
        assert PART_COLORS['NonCodingOther'] in svg
        
        # Other should NOT have chevrons
        path_count = svg.count('<path')
        assert path_count == 0, "NonCodingOther should not have chevrons"
    
    def test_part_svg_contains_all_required_elements(self):
        """Test that part SVG contains all required elements per requirements."""
        part = Part(
            id='test-6',
            name='TestPart',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor='testuser'
        )
        
        svg = generate_part_svg(part)
        
        # Requirements 2.1: Visual representation indicating type
        assert PART_COLORS['Coding'] in svg
        
        # Requirements 2.3: Display orientation and boundaries
        assert '<rect' in svg  # Rectangle shows boundaries
        
        # Requirements 2.5: Display overhang sequences at part ends
        assert "5'-AATG" in svg
        assert "GCTT-3'" in svg
    
    def test_custom_dimensions(self):
        """Test SVG generation with custom dimensions."""
        part = Part(
            id='test-7',
            name='Test',
            part_type='Coding',
            sequence='ATCGATCGATCG',
            overhang_5prime='AATG',
            overhang_3prime='GCTT',
            lab_source='Test Lab',
            contributor='testuser'
        )
        
        svg = generate_part_svg(part, width=300, height=100)
        
        # Check that custom dimensions are used
        assert 'width="300"' in svg
        assert 'height="100"' in svg


class TestCassetteSVGGeneration:
    """Tests for cassette SVG generation."""
    
    def test_generate_cassette_svg_with_multiple_parts(self):
        """Test SVG generation for a cassette with multiple parts."""
        parts = [
            Part(
                id='p1',
                name='Promoter',
                part_type='NonCodingPromoter',
                sequence='ATCGATCGATCG',
                overhang_5prime='GGAG',
                overhang_3prime='AATG',
                lab_source='Lab1',
                contributor='user1'
            ),
            Part(
                id='p2',
                name='GFP',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='AATG',
                overhang_3prime='GCTT',
                lab_source='Lab1',
                contributor='user1'
            ),
            Part(
                id='p3',
                name='Terminator',
                part_type='NonCodingTerminator',
                sequence='ATCGATCGATCG',
                overhang_5prime='GCTT',
                overhang_3prime='CGCT',
                lab_source='Lab1',
                contributor='user1'
            )
        ]
        
        svg = generate_cassette_svg(parts)
        
        # Check that SVG is generated
        assert svg.startswith('<svg')
        assert svg.endswith('</svg>')
        
        # Check that all part names are present
        assert 'Promoter' in svg
        assert 'GFP' in svg
        assert 'Terminator' in svg
        
        # Check that colors for each part type are present
        assert PART_COLORS['NonCodingPromoter'] in svg
        assert PART_COLORS['Coding'] in svg
        assert PART_COLORS['NonCodingTerminator'] in svg
        
        # Check for overhang labels at junctions
        assert 'AATG' in svg  # Junction between promoter and GFP
        assert 'GCTT' in svg  # Junction between GFP and terminator
    
    def test_generate_cassette_svg_shows_relative_positions(self):
        """Test that cassette SVG shows relative positions of parts."""
        parts = [
            Part(
                id='p1',
                name='Part1',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='GGAG',
                overhang_3prime='AATG',
                lab_source='Lab1',
                contributor='user1'
            ),
            Part(
                id='p2',
                name='Part2',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='AATG',
                overhang_3prime='GCTT',
                lab_source='Lab1',
                contributor='user1'
            )
        ]
        
        svg = generate_cassette_svg(parts)
        
        # Requirements 2.4: Show relative positions
        # Check that there are multiple rectangles (one for each part)
        rect_count = svg.count('<rect')
        assert rect_count == 2, "Should have one rectangle per part"
    
    def test_generate_cassette_svg_empty_parts(self):
        """Test cassette SVG generation with empty parts list."""
        svg = generate_cassette_svg([])
        
        # Should return a valid SVG with a message
        assert svg.startswith('<svg')
        assert 'Empty cassette' in svg
    
    def test_generate_cassette_svg_single_part(self):
        """Test cassette SVG generation with a single part."""
        parts = [
            Part(
                id='p1',
                name='SinglePart',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='GGAG',
                overhang_3prime='AATG',
                lab_source='Lab1',
                contributor='user1'
            )
        ]
        
        svg = generate_cassette_svg(parts)
        
        # Check that SVG is generated
        assert svg.startswith('<svg')
        assert 'SinglePart' in svg
        
        # Should show both 5' and 3' overhangs
        assert "5'-GGAG" in svg
        assert "AATG-3'" in svg
    
    def test_cassette_svg_truncates_long_names(self):
        """Test that long part names are truncated in cassette view."""
        parts = [
            Part(
                id='p1',
                name='VeryLongPartNameThatShouldBeTruncated',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='GGAG',
                overhang_3prime='AATG',
                lab_source='Lab1',
                contributor='user1'
            )
        ]
        
        svg = generate_cassette_svg(parts)
        
        # Name should be truncated with ellipsis
        assert '...' in svg
    
    def test_cassette_svg_shows_compatibility_indicators(self):
        """Test that cassette SVG shows compatibility indicators between adjacent parts."""
        # Create compatible parts
        compatible_parts = [
            Part(
                id='p1',
                name='Part1',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='GGAG',
                overhang_3prime='AATG',
                lab_source='Lab1',
                contributor='user1'
            ),
            Part(
                id='p2',
                name='Part2',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='AATG',  # Matches previous 3' overhang
                overhang_3prime='GCTT',
                lab_source='Lab1',
                contributor='user1'
            )
        ]
        
        svg = generate_cassette_svg(compatible_parts)
        
        # Requirements 2.4: Indicate compatibility between adjacent parts
        # Should show green checkmark for compatible parts
        assert '✓' in svg, "Should show checkmark for compatible parts"
        assert '#22C55E' in svg or 'green' in svg.lower(), "Checkmark should be green"
    
    def test_cassette_svg_shows_incompatibility_indicators(self):
        """Test that cassette SVG shows incompatibility indicators for mismatched parts."""
        # Create incompatible parts
        incompatible_parts = [
            Part(
                id='p1',
                name='Part1',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='GGAG',
                overhang_3prime='AATG',
                lab_source='Lab1',
                contributor='user1'
            ),
            Part(
                id='p2',
                name='Part2',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='GCTT',  # Does NOT match previous 3' overhang
                overhang_3prime='CGCT',
                lab_source='Lab1',
                contributor='user1'
            )
        ]
        
        svg = generate_cassette_svg(incompatible_parts)
        
        # Requirements 2.4: Indicate compatibility between adjacent parts
        # Should show red X for incompatible parts
        assert '✗' in svg, "Should show X for incompatible parts"
        assert '#EF4444' in svg or 'red' in svg.lower(), "X should be red"
        assert 'Incompatible' in svg, "Should show 'Incompatible' text"
    
    def test_cassette_svg_all_requirements_met(self):
        """Test that cassette SVG meets all requirements from task 6.3."""
        parts = [
            Part(
                id='p1',
                name='Promoter',
                part_type='NonCodingPromoter',
                sequence='ATCGATCGATCG',
                overhang_5prime='GGAG',
                overhang_3prime='AATG',
                lab_source='Lab1',
                contributor='user1'
            ),
            Part(
                id='p2',
                name='GFP',
                part_type='Coding',
                sequence='ATCGATCGATCG',
                overhang_5prime='AATG',
                overhang_3prime='GCTT',
                lab_source='Lab1',
                contributor='user1'
            ),
            Part(
                id='p3',
                name='Terminator',
                part_type='NonCodingTerminator',
                sequence='ATCGATCGATCG',
                overhang_5prime='GCTT',
                overhang_3prime='CGCT',
                lab_source='Lab1',
                contributor='user1'
            )
        ]
        
        svg = generate_cassette_svg(parts)
        
        # Requirement 1: Generate connected part visualizations
        assert svg.startswith('<svg'), "Should generate valid SVG"
        assert svg.count('<rect') == 3, "Should have one rectangle per part"
        
        # Requirement 2: Show relative positions of parts
        # Parts should be positioned next to each other (checked by multiple rectangles)
        assert 'Promoter' in svg
        assert 'GFP' in svg
        assert 'Terminator' in svg
        
        # Requirement 3: Display overhang labels at junctions
        assert 'AATG' in svg, "Should show junction overhang between promoter and GFP"
        assert 'GCTT' in svg, "Should show junction overhang between GFP and terminator"
        
        # Requirement 4: Indicate compatibility between adjacent parts
        assert '✓' in svg, "Should show compatibility indicators"
        
        # Validates Requirement 2.4
        # All parts are compatible, so should have checkmarks
        checkmark_count = svg.count('✓')
        assert checkmark_count == 2, "Should have 2 checkmarks for 2 junctions"


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_darken_color(self):
        """Test color darkening function."""
        # Test with blue color
        original = '#4A90E2'
        darkened = _darken_color(original, 0.3)
        
        # Should return a valid hex color
        assert darkened.startswith('#')
        assert len(darkened) == 7
        
        # Darkened color should have lower RGB values
        orig_r = int(original[1:3], 16)
        dark_r = int(darkened[1:3], 16)
        assert dark_r < orig_r
    
    def test_darken_color_with_hash(self):
        """Test color darkening with hash prefix."""
        result = _darken_color('#FF0000', 0.5)
        assert result.startswith('#')
    
    def test_darken_color_without_hash(self):
        """Test color darkening without hash prefix."""
        result = _darken_color('FF0000', 0.5)
        assert result.startswith('#')


class TestChevronGeneration:
    """Tests for chevron generation."""
    
    def test_coding_parts_have_chevrons(self):
        """Test that Coding parts display chevrons."""
        assert 'Coding' in CHEVRON_TYPES
    
    def test_promoter_parts_have_chevrons(self):
        """Test that Promoter parts display chevrons."""
        assert 'NonCodingPromoter' in CHEVRON_TYPES
    
    def test_terminator_parts_no_chevrons(self):
        """Test that Terminator parts do not display chevrons."""
        assert 'NonCodingTerminator' not in CHEVRON_TYPES
    
    def test_intron_parts_no_chevrons(self):
        """Test that Intron parts do not display chevrons."""
        assert 'NonCodingIntron' not in CHEVRON_TYPES
    
    def test_other_parts_no_chevrons(self):
        """Test that Other parts do not display chevrons."""
        assert 'NonCodingOther' not in CHEVRON_TYPES


class TestColorScheme:
    """Tests for color scheme."""
    
    def test_all_part_types_have_colors(self):
        """Test that all part types have defined colors."""
        for part_type in Part.VALID_PART_TYPES:
            assert part_type in PART_COLORS, f"Missing color for {part_type}"
    
    def test_coding_color_is_blue(self):
        """Test that Coding parts are blue."""
        color = PART_COLORS['Coding']
        # Blue should have high blue component
        b = int(color[5:7], 16)
        assert b > 150, "Coding color should be predominantly blue"
    
    def test_promoter_color_is_green(self):
        """Test that Promoter parts are green."""
        color = PART_COLORS['NonCodingPromoter']
        # Green should have high green component
        g = int(color[3:5], 16)
        assert g > 150, "Promoter color should be predominantly green"
    
    def test_terminator_color_is_red(self):
        """Test that Terminator parts are red."""
        color = PART_COLORS['NonCodingTerminator']
        # Red should have high red component
        r = int(color[1:3], 16)
        assert r > 150, "Terminator color should be predominantly red"
    
    def test_intron_color_is_yellow(self):
        """Test that Intron parts are yellow."""
        color = PART_COLORS['NonCodingIntron']
        # Yellow should have high red and green components
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        assert r > 150 and g > 150, "Intron color should be predominantly yellow"
    
    def test_other_color_is_gray(self):
        """Test that Other parts are gray."""
        color = PART_COLORS['NonCodingOther']
        # Gray should have similar RGB values
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        assert abs(r - g) < 20 and abs(g - b) < 20, "Other color should be gray"
