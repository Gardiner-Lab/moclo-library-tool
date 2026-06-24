"""
Visualization API endpoints.

This module provides REST API endpoints for:
- GET /api/visualize/part/:id - Get part visualization (SVG)
- GET /api/visualize/cassette/:id - Get cassette visualization (SVG)

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

from flask import Blueprint, jsonify, Response
from app.models.part import Part
from app.models.cassette import Cassette
from app.services.authorization import require_auth, require_cassette_ownership
from app.services.visualization import generate_part_svg, generate_cassette_svg

# Create blueprint
visualize_bp = Blueprint('visualize', __name__)


@visualize_bp.route('/part/<part_id>', methods=['GET'])
@require_auth
def visualize_part(user, part_id: str):
    """
    Get SVG visualization of a specific part.
    
    The visualization includes:
    - Colored rectangle based on part type
    - Chevrons for Coding and Promoter types
    - Overhang labels at both ends
    - Part name
    
    Path Parameters:
        part_id: Part ID
    
    Response (200 OK):
        Content-Type: image/svg+xml
        SVG representation of the part
    
    Error Responses:
        401 Unauthorized: Authentication required
        404 Not Found: Part not found
        500 Internal Server Error: Visualization generation failed
    
    Requirements: 2.1, 2.2, 2.3, 2.5
    """
    try:
        # Retrieve part
        part = Part.get_by_id(part_id)
        
        if part is None:
            return jsonify({
                'error': f'Part {part_id} not found'
            }), 404
        
        # Generate SVG visualization
        svg_content = generate_part_svg(part)
        
        # Return SVG with appropriate content type
        return Response(
            svg_content,
            mimetype='image/svg+xml',
            headers={
                'Content-Disposition': f'inline; filename="{part.name}.svg"'
            }
        ), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to generate visualization',
            'message': str(e)
        }), 500


@visualize_bp.route('/cassette/<cassette_id>', methods=['GET'])
@require_cassette_ownership
def visualize_cassette(user, cassette, cassette_id: str):
    """
    Get SVG visualization of a specific cassette.
    
    The visualization shows:
    - All parts in order with their colors
    - Overhang labels at junctions between parts
    - Compatibility indicators (green checkmark for compatible, red X for incompatible)
    - Part names within each part
    - Chevrons for Coding and Promoter types
    
    Path Parameters:
        cassette_id: Cassette ID
    
    Response (200 OK):
        Content-Type: image/svg+xml
        SVG representation of the cassette
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied to cassette
        404 Not Found: Cassette not found
        500 Internal Server Error: Visualization generation failed
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
    """
    try:
        # Get all parts in the cassette
        parts = []
        for part_id in cassette.part_ids:
            part = Part.get_by_id(part_id)
            if part is None:
                return jsonify({
                    'error': f'Part {part_id} not found in cassette'
                }), 404
            parts.append(part)
        
        # Generate SVG visualization
        svg_content = generate_cassette_svg(parts)
        
        # Return SVG with appropriate content type
        return Response(
            svg_content,
            mimetype='image/svg+xml',
            headers={
                'Content-Disposition': f'inline; filename="{cassette.name}.svg"'
            }
        ), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to generate visualization',
            'message': str(e)
        }), 500



@visualize_bp.route('/part/<part_id>/features', methods=['GET'])
@require_auth
def visualize_part_features(user, part_id: str):
    """
    Get cassette-style SVG visualization of a part's features.
    
    For assembled parts that contain Level 0 parts as features,
    this renders them in the same style as cassette visualizations
    (colored blocks for promoter, CDS, terminator, etc.)
    
    Path Parameters:
        part_id: Part ID
    
    Response (200 OK):
        Content-Type: image/svg+xml
    """
    try:
        from app.services.visualization import generate_part_features_svg
        
        part = Part.get_by_id(part_id)
        if part is None:
            return jsonify({'error': f'Part {part_id} not found'}), 404
        
        features = part.features if hasattr(part, 'features') and part.features else []
        
        if not features:
            # Fall back to regular part SVG
            from app.services.visualization import generate_part_svg
            svg_content = generate_part_svg(part, width=800, height=120)
        else:
            svg_content = generate_part_features_svg(features, len(part.sequence))
        
        return Response(
            svg_content,
            mimetype='image/svg+xml'
        ), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
