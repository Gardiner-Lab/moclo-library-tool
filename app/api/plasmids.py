"""
Plasmids API endpoints.

This module provides REST API endpoints for:
- POST /api/plasmids - Assemble cassettes into backbone
- GET /api/plasmids - List user's plasmids
- GET /api/plasmids/:id - Get plasmid details
- DELETE /api/plasmids/:id - Delete plasmid
- POST /api/plasmids/simulate - Simulate assembly
- GET /api/plasmids/:id/export/genbank - Export as GenBank
- GET /api/plasmids/:id/export/fasta - Export as FASTA
- GET /api/plasmids/:id/export/image - Export circular map as PNG
"""

from flask import Blueprint, request, jsonify, send_file
from io import BytesIO
from app.models.backbone import Backbone
from app.models.cassette import Cassette
from app.models.final_plasmid import FinalPlasmid
from app.services.authorization import require_auth
from app.services.plasmid_assembly import (
    assemble_plasmid,
    validate_assembly,
    simulate_assembly,
    AssemblyError
)
from app.services.genbank_parser import format_genbank_output
from app.services.circular_map import generate_circular_map
from app.services.export import svg_to_png


# Create blueprint
plasmids_bp = Blueprint('plasmids', __name__)


@plasmids_bp.route('', methods=['POST'])
@require_auth
def create_plasmid(user):
    """
    Assemble cassettes into a backbone to create a final plasmid.
    
    Request Body:
        {
            "name": "string",
            "backbone_id": "string",
            "cassette_ids": ["string", ...],
            "slots": [1, 2, ...] (optional, auto-assigned if not provided),
            "orientations": ["forward", "reverse", ...] (optional, auto-detected if not provided)
        }
    
    Response (201 Created):
        {
            "plasmid": {
                "id": "string",
                "name": "string",
                "owner_id": "string",
                "backbone_id": "string",
                "cassette_ids": [...],
                "size": number,
                "features": [...],
                "created_at": "ISO8601"
            },
            "message": "Plasmid assembled successfully"
        }
    
    Error Responses:
        400 Bad Request: Invalid input or incompatible cassettes
        401 Unauthorized: Authentication required
        404 Not Found: Backbone or cassette not found
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
        backbone_id = data.get('backbone_id')
        cassette_ids = data.get('cassette_ids', [])
        slots = data.get('slots')
        orientations = data.get('orientations')  # New parameter
        
        # Validate required fields
        if not name or not name.strip():
            return jsonify({
                'error': 'Plasmid name is required'
            }), 400
        
        if not backbone_id:
            return jsonify({
                'error': 'Backbone ID is required'
            }), 400
        
        if not cassette_ids or not isinstance(cassette_ids, list):
            return jsonify({
                'error': 'At least one cassette ID is required'
            }), 400
        
        # Get backbone
        backbone = Backbone.get_by_id(backbone_id)
        if backbone is None:
            return jsonify({
                'error': 'Backbone not found',
                'message': f'Backbone {backbone_id} not found'
            }), 404
        
        # Get cassettes
        cassettes = []
        for cassette_id in cassette_ids:
            cassette = Cassette.get_by_id(cassette_id)
            if cassette is None:
                return jsonify({
                    'error': 'Cassette not found',
                    'message': f'Cassette {cassette_id} not found'
                }), 404
            cassettes.append(cassette)
        
        # Validate assembly
        is_valid, validation_message = validate_assembly(backbone, cassettes, slots)
        if not is_valid:
            return jsonify({
                'error': 'Assembly validation failed',
                'message': validation_message
            }), 400
        
        # Perform assembly
        try:
            plasmid = assemble_plasmid(
                backbone=backbone,
                cassettes=cassettes,
                slots=slots,
                orientations=orientations,
                name=name,
                owner_id=user.id
            )
            
            return jsonify({
                'plasmid': plasmid.to_dict(),
                'message': 'Plasmid assembled successfully'
            }), 201
            
        except AssemblyError as e:
            return jsonify({
                'error': 'Assembly failed',
                'message': str(e)
            }), 400
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@plasmids_bp.route('/simulate', methods=['POST'])
@require_auth
def simulate_plasmid_assembly(user):
    """
    Simulate assembly without creating the plasmid.
    
    Useful for previewing the result before committing.
    
    Request Body:
        {
            "backbone_id": "string",
            "cassette_ids": ["string", ...],
            "slots": [1, 2, ...] (optional)
        }
    
    Response (200 OK):
        {
            "valid": boolean,
            "message": "string",
            "final_size": number,
            "features_count": number,
            "cassette_positions": [
                {
                    "cassette": "string",
                    "slot": number,
                    "position": number
                },
                ...
            ]
        }
    
    Error Responses:
        400 Bad Request: Invalid input
        401 Unauthorized: Authentication required
        404 Not Found: Backbone or cassette not found
    """
    try:
        # Parse request body
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'error': 'Request body must be JSON'
            }), 400
        
        # Extract fields
        backbone_id = data.get('backbone_id')
        cassette_ids = data.get('cassette_ids', [])
        slots = data.get('slots')
        
        # Validate required fields
        if not backbone_id:
            return jsonify({
                'error': 'Backbone ID is required'
            }), 400
        
        if not cassette_ids:
            return jsonify({
                'error': 'At least one cassette ID is required'
            }), 400
        
        # Get backbone
        backbone = Backbone.get_by_id(backbone_id)
        if backbone is None:
            return jsonify({
                'error': 'Backbone not found'
            }), 404
        
        # Get cassettes
        cassettes = []
        for cassette_id in cassette_ids:
            cassette = Cassette.get_by_id(cassette_id)
            if cassette is None:
                return jsonify({
                    'error': 'Cassette not found',
                    'message': f'Cassette {cassette_id} not found'
                }), 404
            cassettes.append(cassette)
        
        # Simulate assembly
        simulation = simulate_assembly(backbone, cassettes, slots)
        
        return jsonify(simulation), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@plasmids_bp.route('', methods=['GET'])
@require_auth
def list_plasmids(user):
    """
    List all plasmids visible to all authenticated users.
    
    Query Parameters:
        include_sequence: Include full sequence (default: false)
    
    Response (200 OK):
        {
            "plasmids": [
                {
                    "id": "string",
                    "name": "string",
                    "size": number,
                    "cassette_count": number,
                    "created_at": "ISO8601"
                },
                ...
            ],
            "count": number
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
    """
    try:
        # Get all plasmids (visible to all users)
        all_plasmids = FinalPlasmid.get_all()
        
        # Check if full sequence should be included
        include_sequence = request.args.get('include_sequence', 'false').lower() == 'true'
        
        # Convert to dictionaries
        plasmids_data = []
        for plasmid in all_plasmids:
            data = plasmid.to_dict()
            
            # Remove sequence if not requested
            if not include_sequence:
                data.pop('assembled_sequence', None)
            
            plasmids_data.append(data)
        
        return jsonify({
            'plasmids': plasmids_data,
            'count': len(plasmids_data)
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@plasmids_bp.route('/<plasmid_id>', methods=['GET'])
@require_auth
def get_plasmid(user, plasmid_id):
    """
    Get detailed information about a specific plasmid.
    
    Path Parameters:
        plasmid_id: Plasmid ID
    
    Response (200 OK):
        {
            "id": "string",
            "name": "string",
            "owner_id": "string",
            "backbone_id": "string",
            "cassette_ids": [...],
            "assembled_sequence": "string",
            "size": number,
            "features": [...],
            "metadata": {...},
            "created_at": "ISO8601"
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied
        404 Not Found: Plasmid not found
    """
    try:
        # Get plasmid
        plasmid = FinalPlasmid.get_by_id(plasmid_id)
        
        if plasmid is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Plasmid {plasmid_id} not found'
            }), 404
        
        # Check ownership or if it's a system plasmid
        from app.models.user import User
        system_user = User.get_by_username('system')
        is_system_plasmid = system_user and plasmid.owner_id == system_user.id
        
        if plasmid.owner_id != user.id and not is_system_plasmid:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied to this plasmid'
            }), 403
        
        return jsonify(plasmid.to_dict()), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@plasmids_bp.route('/<plasmid_id>', methods=['DELETE'])
@require_auth
def delete_plasmid(user, plasmid_id):
    """
    Delete a plasmid.
    
    Path Parameters:
        plasmid_id: Plasmid ID
    
    Response (200 OK):
        {
            "message": "Plasmid deleted successfully"
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied or cannot delete system plasmids
        404 Not Found: Plasmid not found
    """
    try:
        # Get plasmid
        plasmid = FinalPlasmid.get_by_id(plasmid_id)
        
        if plasmid is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Plasmid {plasmid_id} not found'
            }), 404
        
        # Check if this is a system plasmid
        from app.models.user import User
        system_user = User.get_by_username('system')
        if system_user and plasmid.owner_id == system_user.id:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Cannot delete system plasmids (shared examples)'
            }), 403
        
        # Check ownership
        if plasmid.owner_id != user.id:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied to this plasmid'
            }), 403
        
        # Delete plasmid
        plasmid.delete()
        
        return jsonify({
            'message': 'Plasmid deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@plasmids_bp.route('/<plasmid_id>/export/genbank', methods=['GET'])
@require_auth
def export_genbank(user, plasmid_id):
    """
    Export a plasmid as GenBank format.
    
    Path Parameters:
        plasmid_id: Plasmid ID
    
    Response (200 OK):
        Content-Type: text/plain
        Content-Disposition: attachment; filename="<plasmid_name>.gb"
        
        GenBank formatted text file
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied
        404 Not Found: Plasmid not found
    """
    try:
        # Get plasmid
        plasmid = FinalPlasmid.get_by_id(plasmid_id)
        
        if plasmid is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Plasmid {plasmid_id} not found'
            }), 404
        
        # Check ownership or if it's a system plasmid
        from app.models.user import User
        system_user = User.get_by_username('system')
        is_system_plasmid = system_user and plasmid.owner_id == system_user.id
        
        if plasmid.owner_id != user.id and not is_system_plasmid:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied to this plasmid'
            }), 403
        
        # Generate GenBank content
        genbank_content = format_genbank_output(
            name=plasmid.name,
            sequence=plasmid.assembled_sequence,
            features=plasmid.features,
            description=f"MoClo assembled plasmid - {plasmid.metadata.get('assembly_method', 'Golden Gate')}",
            topology='circular'
        )
        
        # Create file-like object
        genbank_bytes = BytesIO(genbank_content.encode('utf-8'))
        
        # Generate filename
        filename = f"{plasmid.name.replace(' ', '_')}.gb"
        
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


@plasmids_bp.route('/<plasmid_id>/export/fasta', methods=['GET'])
@require_auth
def export_fasta(user, plasmid_id):
    """
    Export a plasmid as FASTA format.
    
    Path Parameters:
        plasmid_id: Plasmid ID
    
    Response (200 OK):
        Content-Type: text/plain
        Content-Disposition: attachment; filename="<plasmid_name>.fasta"
        
        FASTA formatted text file
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied
        404 Not Found: Plasmid not found
    """
    try:
        # Get plasmid
        plasmid = FinalPlasmid.get_by_id(plasmid_id)
        
        if plasmid is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Plasmid {plasmid_id} not found'
            }), 404
        
        # Check ownership or if it's a system plasmid
        from app.models.user import User
        system_user = User.get_by_username('system')
        is_system_plasmid = system_user and plasmid.owner_id == system_user.id
        
        if plasmid.owner_id != user.id and not is_system_plasmid:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied to this plasmid'
            }), 403
        
        # Generate FASTA content
        fasta_lines = [f">{plasmid.name}"]
        
        # Wrap sequence at 60 characters per line
        sequence = plasmid.assembled_sequence
        for i in range(0, len(sequence), 60):
            fasta_lines.append(sequence[i:i+60])
        
        fasta_content = '\n'.join(fasta_lines)
        
        # Create file-like object
        fasta_bytes = BytesIO(fasta_content.encode('utf-8'))
        
        # Generate filename
        filename = f"{plasmid.name.replace(' ', '_')}.fasta"
        
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


@plasmids_bp.route('/<plasmid_id>/export/image', methods=['GET'])
@require_auth
def export_image(user, plasmid_id):
    """
    Export a plasmid as a circular map PNG image with cassette visualizations.
    
    Path Parameters:
        plasmid_id: Plasmid ID
    
    Query Parameters:
        width: Image width in pixels (optional, default: 800)
        format: 'circular' or 'linear' (optional, default: circular)
        include_cassettes: Include cassette images (optional, default: true)
    
    Response (200 OK):
        Content-Type: image/png
        Content-Disposition: attachment; filename="<plasmid_name>.png"
        
        PNG image file
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied
        404 Not Found: Plasmid not found
    """
    try:
        # Get plasmid
        plasmid = FinalPlasmid.get_by_id(plasmid_id)
        
        if plasmid is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Plasmid {plasmid_id} not found'
            }), 404
        
        # Check ownership or if it's a system plasmid
        from app.models.user import User
        system_user = User.get_by_username('system')
        is_system_plasmid = system_user and plasmid.owner_id == system_user.id
        
        if plasmid.owner_id != user.id and not is_system_plasmid:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied to this plasmid'
            }), 403
        
        # Get parameters
        width = request.args.get('width', default=800, type=int)
        map_format = request.args.get('format', default='circular')
        include_cassettes = request.args.get('include_cassettes', default='true').lower() == 'true'
        
        # Validate width
        if width < 100 or width > 4000:
            return jsonify({
                'error': 'Width must be between 100 and 4000 pixels'
            }), 400
        
        # Generate SVG map
        # Prepare cassette regions for highlighting
        cassette_regions = []
        if plasmid.metadata and plasmid.metadata.get('cassette_positions'):
            for pos_info in plasmid.metadata['cassette_positions']:
                cassette_regions.append({
                    'start': pos_info.get('start', 0),
                    'end': pos_info.get('end', 0),
                    'name': pos_info.get('cassette_name', 'Cassette')
                })
        
        svg_content = generate_circular_map(
            plasmid_name=plasmid.name,
            sequence=plasmid.assembled_sequence,
            features=plasmid.features,
            width=width,
            cassette_regions=cassette_regions if cassette_regions else None
        )
        
        # Convert to PNG
        try:
            from app.services.export import create_composite_plasmid_image
            
            if include_cassettes and plasmid.cassette_ids:
                # Get cassette objects
                cassettes = []
                for cassette_id in plasmid.cassette_ids:
                    cassette = Cassette.get_by_id(cassette_id)
                    if cassette:
                        cassettes.append(cassette)
                
                # Create composite image with cassettes
                png_data = create_composite_plasmid_image(
                    plasmid_svg=svg_content,
                    cassettes=cassettes,
                    plasmid_name=plasmid.name,
                    output_width=width
                )
            else:
                # Just the plasmid map
                png_data = svg_to_png(svg_content, output_width=width)
                
        except ImportError as e:
            return jsonify({
                'error': 'Image export not available',
                'message': str(e)
            }), 503
        
        # Create file-like object
        image_bytes = BytesIO(png_data)
        
        # Generate filename
        filename = f"{plasmid.name.replace(' ', '_')}_map.png"
        
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

@plasmids_bp.route('/<plasmid_id>/translation', methods=['GET'])
@require_auth
def get_plasmid_translation(user, plasmid_id):
    """
    Get level-aware translation analysis for a plasmid.
    
    For Level 1 plasmids: returns single reading frame from the cassette.
    For Level 2+ plasmids: returns per-cassette translation data, recognizing
    that each cassette is an independent transcription unit with its own
    reading frame.
    
    Translation data from Level 0 parts is preserved through the hierarchy.
    
    Path Parameters:
        plasmid_id: Plasmid ID
    
    Response (200 OK):
        {
            "plasmid_id": "string",
            "plasmid_name": "string",
            "plasmid_level": number,
            "total_reading_frames": number,
            "transcription_units": [
                {
                    "cassette_id": "string",
                    "cassette_name": "string",
                    "cassette_level": "string",
                    "translation": {
                        "has_coding": bool,
                        "protein_sequence": "string",
                        "start_codon_pos": number,
                        ...
                    }
                },
                ...
            ],
            "warnings": [...]
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        404 Not Found: Plasmid not found
    """
    try:
        # Get plasmid
        plasmid = FinalPlasmid.get_by_id(plasmid_id)
        
        if plasmid is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Plasmid {plasmid_id} not found'
            }), 404
        
        # Check if translation data is already stored in metadata
        if plasmid.metadata and plasmid.metadata.get('translation'):
            translation = plasmid.metadata['translation']
            translation['plasmid_id'] = plasmid.id
            translation['plasmid_name'] = plasmid.name
            return jsonify(translation), 200
        
        # Compute on demand if not stored
        from app.services.translation import analyze_plasmid_translation
        
        # Get cassettes
        cassettes = []
        for cassette_id in plasmid.cassette_ids:
            cassette = Cassette.get_by_id(cassette_id)
            if cassette:
                cassettes.append(cassette)
        
        # Determine level
        moclo_level = plasmid.metadata.get('moclo_level', 1) if plasmid.metadata else 1
        
        # Analyze
        translation = analyze_plasmid_translation(
            plasmid_sequence=plasmid.assembled_sequence,
            cassettes=cassettes,
            plasmid_level=moclo_level
        )
        
        translation['plasmid_id'] = plasmid.id
        translation['plasmid_name'] = plasmid.name
        
        return jsonify(translation), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500
