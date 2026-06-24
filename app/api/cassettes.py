"""
Cassettes API endpoints.

This module provides REST API endpoints for:
- GET /api/cassettes - List user's cassettes
- GET /api/cassettes/:id - Get cassette details
- POST /api/cassettes - Create new cassette
- DELETE /api/cassettes/:id - Delete cassette
- GET /api/cassettes/:id/export/fasta - Export as FASTA
- GET /api/cassettes/:id/export/genbank - Export as GenBank
- GET /api/cassettes/:id/export/image - Export as image

Requirements: 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3
"""

from flask import Blueprint, request, jsonify, send_file
from io import BytesIO
from app.models.cassette import Cassette
from app.models.part import Part
from app.models.backbone import Backbone
from app.services.authorization import require_auth, require_cassette_ownership
from app.services.assembly import (
    create_cassette,
    validate_parts_for_assembly,
    AssemblyError
)
from app.services.export import (
    generate_fasta,
    generate_genbank,
    generate_cassette_image
)
from app.services.backbone_compatibility import find_compatible_backbones

# Create blueprint
cassettes_bp = Blueprint('cassettes', __name__)


@cassettes_bp.route('', methods=['GET'])
@require_auth
def list_cassettes(user):
    """
    List all cassettes owned by the authenticated user plus shared system cassettes.
    
    Response (200 OK):
        {
            "cassettes": [
                {
                    "id": "string",
                    "name": "string",
                    "owner_id": "string",
                    "part_ids": ["string", ...],
                    "assembled_sequence": "string",
                    "created_at": "ISO8601 timestamp",
                    "length": number,
                    "part_count": number
                },
                ...
            ],
            "count": number
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
    
    Requirements: 8.2
    """
    try:
        # Get cassettes owned by this user
        user_cassettes = Cassette.get_by_owner(user.id)
        
        # Get system user cassettes (shared examples)
        from app.models.user import User
        system_user = User.get_by_username('system')
        system_cassettes = []
        if system_user:
            system_cassettes = Cassette.get_by_owner(system_user.id)
        
        # Combine both lists (user cassettes first, then system cassettes)
        all_cassettes = user_cassettes + system_cassettes
        
        # Convert to dictionaries
        cassettes_data = [cassette.to_dict() for cassette in all_cassettes]
        
        return jsonify({
            'cassettes': cassettes_data,
            'count': len(cassettes_data)
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@cassettes_bp.route('/<cassette_id>', methods=['GET'])
@require_cassette_ownership
def get_cassette(user, cassette, cassette_id):
    """
    Get detailed information about a specific cassette.
    
    Path Parameters:
        cassette_id: Cassette ID
    
    Response (200 OK):
        {
            "id": "string",
            "name": "string",
            "owner_id": "string",
            "part_ids": ["string", ...],
            "assembled_sequence": "string",
            "created_at": "ISO8601 timestamp",
            "length": number,
            "part_count": number,
            "parts": [
                {
                    "id": "string",
                    "name": "string",
                    "part_type": "string",
                    "overhang_5prime": "string",
                    "overhang_3prime": "string",
                    ...
                },
                ...
            ]
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied to cassette
        404 Not Found: Cassette not found
    
    Requirements: 5.5, 8.2, 8.3
    """
    try:
        # Get cassette data
        cassette_data = cassette.to_dict()
        
        # Get part details
        parts = []
        for part_id in cassette.part_ids:
            part = Part.get_by_id(part_id)
            if part:
                parts.append(part.to_dict())
        
        cassette_data['parts'] = parts
        
        # Add translation analysis for coding sequences
        from app.services.translation import analyze_coding_sequence, get_part_boundaries_from_cassette
        from app.services.assembly import disassemble_cassette
        
        try:
            cassette_parts = disassemble_cassette(cassette)
            part_boundaries = get_part_boundaries_from_cassette(cassette_parts, cassette.assembled_sequence)
            translation_analysis = analyze_coding_sequence(cassette.assembled_sequence, part_boundaries)
            cassette_data['translation_analysis'] = translation_analysis
        except Exception as trans_error:
            # Don't fail the whole request if translation analysis fails
            cassette_data['translation_analysis'] = {
                'error': str(trans_error),
                'has_coding': False
            }
        
        return jsonify(cassette_data), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@cassettes_bp.route('', methods=['POST'])
@require_auth
def create_new_cassette(user):
    """
    Create a new cassette from a list of parts.
    
    Request Body:
        {
            "name": "string",
            "part_ids": ["string", "string", ...]
        }
    
    Response (201 Created):
        {
            "cassette": {
                "id": "string",
                "name": "string",
                "owner_id": "string",
                "part_ids": ["string", ...],
                "assembled_sequence": "string",
                "created_at": "ISO8601 timestamp",
                "length": number,
                "part_count": number
            },
            "message": "Cassette created successfully"
        }
    
    Error Responses:
        400 Bad Request: Invalid or missing fields, incompatible parts
        401 Unauthorized: Authentication required
        404 Not Found: One or more parts not found
    
    Requirements: 5.1, 5.2, 5.3, 5.4
    """
    try:
        # Parse request body
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'error': 'Request body must be JSON'
            }), 400
        
        # Extract fields
        name = data.get('name')
        part_ids = data.get('part_ids')
        
        # Validate required fields
        if not name or not name.strip():
            return jsonify({
                'error': 'Cassette name is required'
            }), 400
        
        if not part_ids or not isinstance(part_ids, list):
            return jsonify({
                'error': 'part_ids must be a non-empty array'
            }), 400
        
        # Validate parts for assembly
        validation = validate_parts_for_assembly(part_ids)
        
        if not validation['valid']:
            # Check if it's a "not found" error
            if 'not found' in validation['error']:
                return jsonify({
                    'error': validation['error']
                }), 404
            
            # Otherwise it's a validation error (incompatible parts, etc.)
            return jsonify({
                'error': validation['error']
            }), 400
        
        # Create the cassette
        try:
            cassette = create_cassette(
                name=name,
                owner_id=user.id,
                parts=validation['parts']
            )
            
            return jsonify({
                'cassette': cassette.to_dict(),
                'message': 'Cassette created successfully'
            }), 201
            
        except AssemblyError as e:
            return jsonify({
                'error': str(e)
            }), 400
        
        except ValueError as e:
            return jsonify({
                'error': str(e)
            }), 400
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@cassettes_bp.route('/<cassette_id>', methods=['DELETE'])
@require_cassette_ownership
def delete_cassette(user, cassette, cassette_id):
    """
    Delete a cassette.
    
    Path Parameters:
        cassette_id: Cassette ID
    
    Response (200 OK):
        {
            "message": "Cassette deleted successfully"
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied to cassette or cannot delete system cassettes
        404 Not Found: Cassette not found
    
    Requirements: 8.2, 8.3
    """
    try:
        # Check if this is a system cassette
        from app.models.user import User
        system_user = User.get_by_username('system')
        if system_user and cassette.owner_id == system_user.id:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Cannot delete system cassettes (shared examples)'
            }), 403
        
        # Verify user owns this cassette
        if cassette.owner_id != user.id:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied to cassette'
            }), 403
        
        # Delete the cassette
        cassette.delete()
        
        return jsonify({
            'message': 'Cassette deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@cassettes_bp.route('/<cassette_id>/export/fasta', methods=['GET'])
@require_cassette_ownership
def export_fasta(user, cassette, cassette_id):
    """
    Export a cassette as FASTA format.
    
    Path Parameters:
        cassette_id: Cassette ID
    
    Response (200 OK):
        Content-Type: text/plain
        Content-Disposition: attachment; filename="<cassette_name>.fasta"
        
        FASTA formatted text file
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied to cassette
        404 Not Found: Cassette not found
    
    Requirements: 6.2
    """
    try:
        # Generate FASTA content
        fasta_content = generate_fasta(cassette)
        
        # Create a file-like object
        fasta_bytes = BytesIO(fasta_content.encode('utf-8'))
        
        # Generate filename (replace spaces with underscores)
        filename = f"{cassette.name.replace(' ', '_')}.fasta"
        
        return send_file(
            fasta_bytes,
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to generate FASTA export',
            'message': str(e)
        }), 500


@cassettes_bp.route('/<cassette_id>/export/genbank', methods=['GET'])
@require_cassette_ownership
def export_genbank(user, cassette, cassette_id):
    """
    Export a cassette as GenBank format.
    
    Path Parameters:
        cassette_id: Cassette ID
    
    Response (200 OK):
        Content-Type: text/plain
        Content-Disposition: attachment; filename="<cassette_name>.gb"
        
        GenBank formatted text file
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied to cassette
        404 Not Found: Cassette not found
    
    Requirements: 6.3
    """
    try:
        # Generate GenBank content
        genbank_content = generate_genbank(cassette)
        
        # Create a file-like object
        genbank_bytes = BytesIO(genbank_content.encode('utf-8'))
        
        # Generate filename (replace spaces with underscores)
        filename = f"{cassette.name.replace(' ', '_')}.gb"
        
        return send_file(
            genbank_bytes,
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to generate GenBank export',
            'message': str(e)
        }), 500


@cassettes_bp.route('/<cassette_id>/export/image', methods=['GET'])
@require_cassette_ownership
def export_image(user, cassette, cassette_id):
    """
    Export a cassette as a PNG image.
    
    Path Parameters:
        cassette_id: Cassette ID
    
    Query Parameters:
        width: Image width in pixels (optional, default: 800)
    
    Response (200 OK):
        Content-Type: image/png
        Content-Disposition: attachment; filename="<cassette_name>.png"
        
        PNG image file
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied to cassette
        404 Not Found: Cassette not found
        500 Internal Server Error: Image generation failed
    
    Requirements: 6.1, 6.4
    """
    try:
        # Get optional width parameter
        width = request.args.get('width', default=800, type=int)
        
        # Validate width
        if width < 100 or width > 4000:
            return jsonify({
                'error': 'Width must be between 100 and 4000 pixels'
            }), 400
        
        # Generate image
        try:
            image_data = generate_cassette_image(cassette, width=width)
        except ImportError as e:
            return jsonify({
                'error': 'Image export not available',
                'message': str(e)
            }), 503
        except ValueError as e:
            return jsonify({
                'error': 'Failed to generate image',
                'message': str(e)
            }), 500
        
        # Create a file-like object
        image_bytes = BytesIO(image_data)
        
        # Generate filename (replace spaces with underscores)
        filename = f"{cassette.name.replace(' ', '_')}.png"
        
        return send_file(
            image_bytes,
            mimetype='image/png',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to generate image export',
            'message': str(e)
        }), 500


@cassettes_bp.route('/<cassette_id>/compatible-backbones', methods=['GET'])
@require_cassette_ownership
def get_compatible_backbones(user, cassette, cassette_id):
    """
    Get all backbones compatible with a cassette.
    
    Path Parameters:
        cassette_id: Cassette ID
    
    Response (200 OK):
        {
            "cassette_id": "string",
            "cassette_name": "string",
            "compatible_backbones": [
                {
                    "backbone": {...},
                    "compatibility": {
                        "compatible": true,
                        "reason": "string",
                        "matching_slots": [1, 2],
                        "score": 100
                    }
                },
                ...
            ],
            "count": number
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied to cassette
        404 Not Found: Cassette not found
    """
    try:
        # Get all backbones
        backbones = Backbone.get_all()
        
        # Find compatible backbones
        compatible = find_compatible_backbones(cassette, backbones)
        
        # Format response
        compatible_data = []
        for item in compatible:
            bb = item['backbone']
            comp = item['compatibility']
            compatible_data.append({
                'backbone_id': bb.id,
                'backbone_name': bb.name,
                'backbone_length': bb.size,
                'slot_count': bb.cassette_slots,
                'compatibility_score': comp['score'],
                'matching_slots': comp['matching_slots'],
                'reason': comp['reason'],
                'backbone': bb.to_dict(),
                'compatibility': comp
            })
        
        return jsonify({
            'cassette_id': cassette.id,
            'cassette_name': cassette.name,
            'compatible_backbones': compatible_data,
            'count': len(compatible_data)
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500
