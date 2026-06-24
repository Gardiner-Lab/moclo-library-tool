"""
Backbones API endpoints.

This module provides REST API endpoints for:
- POST /api/backbones - Upload new backbone from GenBank file
- GET /api/backbones - List user's backbones
- GET /api/backbones/:id - Get backbone details
- DELETE /api/backbones/:id - Delete backbone
- GET /api/backbones/:id/sites - Get restriction sites
- GET /api/backbones/:id/compatible-cassettes - Get compatible cassettes
"""

from flask import Blueprint, request, jsonify
from app.models.backbone import Backbone
from app.models.cassette import Cassette
from app.services.authorization import require_auth
from app.services.genbank_parser import (
    parse_genbank_file,
    validate_genbank_content,
    GenBankParseError
)
from app.services.restriction_sites import (
    find_moclo_sites,
    identify_cassette_slots,
    validate_moclo_backbone
)
from app.services.backbone_compatibility import find_compatible_cassettes


# Create blueprint
backbones_bp = Blueprint('backbones', __name__)


@backbones_bp.route('', methods=['POST'])
@require_auth
def upload_backbone(user):
    """
    Upload a new backbone from a GenBank file.
    
    Request:
        Content-Type: multipart/form-data
        Fields:
            - file: GenBank file (.gb, .gbk)
            - name: Backbone name (optional, uses file name if not provided)
            - description: Description (optional)
            - enzyme: Restriction enzyme to detect (default: BsaI)
    
    Response (201 Created):
        {
            "backbone": {
                "id": "string",
                "name": "string",
                "owner_id": "string",
                "sequence": "string",
                "size": number,
                "description": "string",
                "restriction_sites": [...],
                "cassette_slots": number,
                "created_at": "ISO8601"
            },
            "message": "Backbone uploaded successfully"
        }
    
    Error Responses:
        400 Bad Request: Invalid file or format
        401 Unauthorized: Authentication required
        500 Internal Server Error: Processing failed
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Please upload a GenBank file'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please select a file to upload'
            }), 400
        
        # Check file extension
        if not file.filename.lower().endswith(('.gb', '.gbk', '.genbank')):
            return jsonify({
                'error': 'Invalid file type',
                'message': 'File must be a GenBank file (.gb, .gbk, .genbank)'
            }), 400
        
        # Read file content
        file_content = file.read().decode('utf-8')
        
        # Validate GenBank format
        is_valid, error_message = validate_genbank_content(file_content)
        if not is_valid:
            return jsonify({
                'error': 'Invalid GenBank file',
                'message': error_message
            }), 400
        
        # Parse GenBank file
        try:
            parsed_data = parse_genbank_file(file_content)
        except GenBankParseError as e:
            return jsonify({
                'error': 'Failed to parse GenBank file',
                'message': str(e)
            }), 400
        
        # Get name from form or use file name
        name = request.form.get('name')
        if not name:
            name = file.filename.rsplit('.', 1)[0]
        
        # Get description
        description = request.form.get('description', parsed_data.get('description', ''))
        
        # Get enzyme (default to BsaI)
        enzyme = request.form.get('enzyme', 'BsaI')
        
        # Find restriction sites
        sequence = parsed_data['sequence']
        sites = find_moclo_sites(sequence, enzyme)
        
        # Validate as MoClo backbone
        is_valid_backbone, validation_message, _ = validate_moclo_backbone(sequence, enzyme)
        
        if not is_valid_backbone:
            return jsonify({
                'error': 'Not a valid MoClo backbone',
                'message': validation_message,
                'suggestion': f'The sequence should contain at least 2 {enzyme} sites that form valid cassette insertion slots'
            }), 400
        
        # Identify cassette slots (for validation and response, but don't modify sites)
        slots = identify_cassette_slots(sites)
        
        # Note: We store the raw restriction sites without slot_number
        # The identify_cassette_slots function will be called when needed
        # to determine slot information from the sites
        
        # Extract additional metadata from GenBank annotations
        metadata = parsed_data.get('metadata', {})
        
        # Try to extract contributor from GenBank comments or source
        contributor = None
        donor_organism = metadata.get('organism', '')
        lab_source = None
        reference = None
        
        # Auto-detect overhangs from first slot
        overhang_5prime = None
        overhang_3prime = None
        if slots and len(slots) > 0:
            first_slot = slots[0]
            overhang_5prime = first_slot.get('expected_overhang_5prime')
            overhang_3prime = first_slot.get('expected_overhang_3prime')
        
        # Check for additional info in features or annotations
        if parsed_data.get('features'):
            for feature in parsed_data['features']:
                qualifiers = feature.get('qualifiers', {})
                if 'note' in qualifiers and not contributor:
                    # Try to extract contributor from notes
                    note = qualifiers['note']
                    if isinstance(note, list):
                        note = ' '.join(note)
                    if 'contributor' in note.lower() or 'source' in note.lower():
                        contributor = note[:100]  # Limit length
        
        # Create backbone with all available metadata
        backbone = Backbone.create(
            name=name,
            owner_id=user.id,
            sequence=sequence,
            description=description,
            genbank_data=parsed_data,
            restriction_sites=sites,
            contributor=contributor or user.username,  # Default to uploader
            donor_organism=donor_organism if donor_organism else None,
            lab_source=lab_source,
            overhang_5prime=overhang_5prime,
            overhang_3prime=overhang_3prime,
            reference=reference
        )
        
        return jsonify({
            'backbone': backbone.to_dict(),
            'message': f'Backbone uploaded successfully with {len(slots)} cassette slot(s)'
        }), 201
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@backbones_bp.route('', methods=['GET'])
@require_auth
def list_backbones(user):
    """
    List all backbones (user's own backbones plus system backbones).
    
    Query Parameters:
        - include_sequence: Include full sequence (default: false)
        - mine_only: Only show user's backbones (default: false)
    
    Response (200 OK):
        {
            "backbones": [
                {
                    "id": "string",
                    "name": "string",
                    "size": number,
                    "cassette_slots": number,
                    "description": "string",
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
        # Check if user wants only their own backbones
        mine_only = request.args.get('mine_only', 'false').lower() == 'true'
        
        if mine_only:
            # Get only user's backbones
            backbones = Backbone.get_by_owner(user.id)
        else:
            # Get all backbones (user's + system backbones)
            backbones = Backbone.get_all()
        
        # Check if full sequence should be included
        include_sequence = request.args.get('include_sequence', 'false').lower() == 'true'
        
        # Convert to dictionaries
        backbones_data = []
        for backbone in backbones:
            data = backbone.to_dict()
            
            # Remove sequence if not requested (can be large)
            if not include_sequence:
                data.pop('sequence', None)
                data.pop('genbank_data', None)
            
            backbones_data.append(data)
        
        return jsonify({
            'backbones': backbones_data,
            'count': len(backbones_data)
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@backbones_bp.route('/<backbone_id>', methods=['GET'])
@require_auth
def get_backbone(user, backbone_id):
    """
    Get detailed information about a specific backbone.
    
    Path Parameters:
        backbone_id: Backbone ID
    
    Response (200 OK):
        {
            "id": "string",
            "name": "string",
            "owner_id": "string",
            "sequence": "string",
            "size": number,
            "description": "string",
            "genbank_data": {...},
            "restriction_sites": [...],
            "cassette_slots": number,
            "features": [...],
            "created_at": "ISO8601"
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        404 Not Found: Backbone not found
    """
    try:
        # Get backbone
        backbone = Backbone.get_by_id(backbone_id)
        
        if backbone is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Backbone {backbone_id} not found'
            }), 404
        
        # Allow access to own backbones and system backbones
        # (System backbones are shared reference backbones)
        
        return jsonify(backbone.to_dict()), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@backbones_bp.route('/<backbone_id>', methods=['DELETE'])
@require_auth
def delete_backbone(user, backbone_id):
    """
    Delete a backbone.
    
    Path Parameters:
        backbone_id: Backbone ID
    
    Response (200 OK):
        {
            "message": "Backbone deleted successfully"
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied
        404 Not Found: Backbone not found
    """
    try:
        # Get backbone
        backbone = Backbone.get_by_id(backbone_id)
        
        if backbone is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Backbone {backbone_id} not found'
            }), 404
        
        # Check if this is a system backbone
        from app.models.user import User
        system_user = User.get_by_username('system')
        if system_user and backbone.owner_id == system_user.id:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Cannot delete system backbones (shared examples)'
            }), 403
        
        # Check ownership
        if backbone.owner_id != user.id:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied to this backbone'
            }), 403
        
        # Delete backbone
        backbone.delete()
        
        return jsonify({
            'message': 'Backbone deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@backbones_bp.route('/<backbone_id>', methods=['PUT', 'PATCH'])
@require_auth
def update_backbone(user, backbone_id):
    """
    Update backbone metadata.
    
    Path Parameters:
        backbone_id: Backbone ID
    
    Request Body (JSON):
        {
            "name": "string (optional)",
            "description": "string (optional)",
            "plasmid_id": "string (optional)",
            "level": "string (optional)",
            "unit": "string (optional)",
            "antibiotic": "string (optional)",
            "ori_ecoli": "string (optional)",
            "ori_agro": "string (optional)",
            "host_strain": "string (optional)",
            "contributor": "string (optional)",
            "donor_organism": "string (optional)",
            "lab_source": "string (optional)",
            "reference": "string (optional)",
            "location_80": "string (optional)",
            "location_96_plate": "string (optional)",
            "primer_for_seq": "string (optional)",
            "sequenced": "string (optional)",
            "comments": "string (optional)"
        }
    
    Response (200 OK):
        {
            "backbone": {...},
            "message": "Backbone updated successfully"
        }
    
    Error Responses:
        400 Bad Request: Invalid data
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied
        404 Not Found: Backbone not found
    """
    try:
        # Get backbone
        backbone = Backbone.get_by_id(backbone_id)
        
        if backbone is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Backbone {backbone_id} not found'
            }), 404
        
        # Check ownership
        if backbone.owner_id != user.id:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied to this backbone'
            }), 403
        
        # Get update data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'Bad request',
                'message': 'No data provided'
            }), 400
        
        # Update fields
        from app.models.database import get_connection
        import json
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Build update query dynamically based on provided fields
        update_fields = []
        update_values = []
        
        # Basic fields
        if 'name' in data:
            update_fields.append('name = ?')
            update_values.append(data['name'])
        
        if 'description' in data:
            update_fields.append('description = ?')
            update_values.append(data['description'])
        
        # Metadata fields
        metadata_fields = [
            'plasmid_id', 'level', 'unit', 'antibiotic',
            'ori_ecoli', 'ori_agro', 'host_strain',
            'contributor', 'donor_organism', 'lab_source',
            'reference', 'location_80', 'location_96_plate',
            'primer_for_seq', 'sequenced', 'comments'
        ]
        
        for field in metadata_fields:
            if field in data:
                update_fields.append(f'{field} = ?')
                update_values.append(data[field])
        
        if not update_fields:
            return jsonify({
                'error': 'Bad request',
                'message': 'No valid fields to update'
            }), 400
        
        # Add backbone_id to values
        update_values.append(backbone_id)
        
        # Execute update
        query = f"UPDATE backbones SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, update_values)
        conn.commit()
        conn.close()
        
        # Get updated backbone
        updated_backbone = Backbone.get_by_id(backbone_id)
        
        return jsonify({
            'backbone': updated_backbone.to_dict(),
            'message': 'Backbone updated successfully'
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@backbones_bp.route('/<backbone_id>/sites', methods=['GET'])
@require_auth
def get_restriction_sites(user, backbone_id):
    """
    Get restriction sites for a backbone.
    
    Path Parameters:
        backbone_id: Backbone ID
    
    Response (200 OK):
        {
            "backbone_id": "string",
            "backbone_name": "string",
            "sites": [
                {
                    "enzyme": "string",
                    "position": number,
                    "strand": "string",
                    "recognition_site": "string",
                    "overhang_5prime": "string",
                    "overhang_3prime": "string",
                    "slot_number": number
                },
                ...
            ],
            "slots": [
                {
                    "slot_number": number,
                    "expected_overhang_5prime": "string",
                    "expected_overhang_3prime": "string",
                    "insertion_start": number,
                    "insertion_end": number
                },
                ...
            ],
            "count": number
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        404 Not Found: Backbone not found
    """
    try:
        # Get backbone
        backbone = Backbone.get_by_id(backbone_id)
        
        if backbone is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Backbone {backbone_id} not found'
            }), 404
        
        # Allow access to system backbones
        
        # Get sites and slots
        sites = backbone.restriction_sites
        slots = identify_cassette_slots(sites)
        
        return jsonify({
            'backbone_id': backbone.id,
            'backbone_name': backbone.name,
            'sites': sites,
            'slots': slots,
            'count': len(sites)
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@backbones_bp.route('/<backbone_id>/compatible-cassettes', methods=['GET'])
@require_auth
def get_compatible_cassettes(user, backbone_id):
    """
    Get all cassettes compatible with a backbone.
    
    Path Parameters:
        backbone_id: Backbone ID
    
    Query Parameters:
        slot: Specific slot number to check (optional)
    
    Response (200 OK):
        {
            "backbone_id": "string",
            "backbone_name": "string",
            "compatible_cassettes": [
                {
                    "cassette": {...},
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
        404 Not Found: Backbone not found
    """
    try:
        # Get backbone
        backbone = Backbone.get_by_id(backbone_id)
        
        if backbone is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Backbone {backbone_id} not found'
            }), 404
        
        # Allow access to system backbones
        
        # Get slot parameter
        slot = request.args.get('slot', type=int)
        
        # Get user's cassettes
        user_cassettes = Cassette.get_by_owner(user.id)
        
        # Get system cassettes (shared examples)
        from app.models.user import User
        system_user = User.get_by_username('system')
        system_cassettes = []
        if system_user:
            system_cassettes = Cassette.get_by_owner(system_user.id)
        
        # Combine both lists
        cassettes = user_cassettes + system_cassettes
        
        # Find compatible cassettes
        compatible = find_compatible_cassettes(backbone, cassettes, slot)
        
        # Format response
        compatible_data = []
        for item in compatible:
            compatible_data.append({
                'cassette': item['cassette'].to_dict(),
                'compatibility': item['compatibility']
            })
        
        return jsonify({
            'backbone_id': backbone.id,
            'backbone_name': backbone.name,
            'compatible_cassettes': compatible_data,
            'count': len(compatible_data)
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()  # Print full traceback to logs
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@backbones_bp.route('/<backbone_id>/download/genbank', methods=['GET'])
@require_auth
def download_backbone_genbank(user, backbone_id):
    """
    Download a backbone as a GenBank file.
    
    Path Parameters:
        backbone_id: Backbone ID
    
    Response (200 OK):
        GenBank file download with Content-Type: text/plain
        Content-Disposition: attachment; filename="{backbone_name}.gb"
    
    Error Responses:
        401 Unauthorized: Authentication required
        404 Not Found: Backbone not found
    """
    from flask import make_response
    from app.services.export import export_backbone_genbank
    
    try:
        # Get backbone
        backbone = Backbone.get_by_id(backbone_id)
        
        if backbone is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Backbone {backbone_id} not found'
            }), 404
        
        # Generate GenBank content
        genbank_content = export_backbone_genbank(backbone_id)
        
        if genbank_content is None:
            return jsonify({
                'error': 'Export failed',
                'message': 'Failed to generate GenBank file'
            }), 500
        
        # Create response with GenBank file
        response = make_response(genbank_content)
        response.headers['Content-Type'] = 'text/plain'
        
        # Sanitize filename
        safe_filename = backbone.name.replace(' ', '_').replace('/', '_')
        response.headers['Content-Disposition'] = f'attachment; filename="{safe_filename}.gb"'
        
        return response
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500
