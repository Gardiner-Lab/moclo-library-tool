"""
Parts API endpoints.

This module provides REST API endpoints for:
- GET /api/parts - List all parts with optional filters
- GET /api/parts/:id - Get part details
- POST /api/parts - Upload new part
- GET /api/parts/:id/compatible - Get compatible parts

Requirements: 1.1, 1.3, 1.5, 3.1, 4.1, 10.1
"""

from flask import Blueprint, request, jsonify, session
from app.models.part import Part
from app.services.validation import validate_part_for_upload, ValidationError
from app.services.compatibility import find_compatible_parts
from functools import wraps
from typing import Callable, Any

# Create blueprint
parts_bp = Blueprint('parts', __name__)


def require_session(f: Callable) -> Callable:
    """
    Decorator to require a valid session for an endpoint.
    
    Returns 401 Unauthorized if session is invalid or missing.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        from app.services.auth import AuthService
        
        session_id = session.get('session_id')
        
        if not session_id or not AuthService.validate_session(session_id):
            return jsonify({
                'error': 'Authentication required'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


@parts_bp.route('', methods=['GET'])
@require_session
def list_parts():
    """
    List all parts with optional filters.
    
    Query Parameters:
        type: Filter by part type (optional)
        search: Search by name or ID (optional)
    
    Response (200 OK):
        {
            "parts": [
                {
                    "id": "string",
                    "name": "string",
                    "part_type": "string",
                    "sequence": "string",
                    "overhang_5prime": "string",
                    "overhang_3prime": "string",
                    "lab_source": "string",
                    "contributor": "string",
                    "upload_date": "ISO8601 timestamp",
                    "description": "string",
                    "length": number
                },
                ...
            ],
            "count": number
        }
    
    Error Responses:
        400 Bad Request: Invalid part type filter
        401 Unauthorized: Authentication required
    
    Requirements: 1.1, 1.3, 1.5
    """
    try:
        # Get query parameters
        part_type = request.args.get('type')
        search_query = request.args.get('search')
        
        # Apply filters
        if part_type:
            # Filter by type
            try:
                parts = Part.filter_by_type(part_type)
            except ValueError as e:
                return jsonify({
                    'error': str(e)
                }), 400
        elif search_query:
            # Search by name or ID
            parts = Part.search(search_query)
        else:
            # Get all parts
            parts = Part.get_all()
        
        # Convert to dictionaries
        parts_data = [part.to_dict() for part in parts]
        
        return jsonify({
            'parts': parts_data,
            'count': len(parts_data)
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error'
        }), 500


@parts_bp.route('/<part_id>', methods=['GET'])
@require_session
def get_part(part_id: str):
    """
    Get detailed information about a specific part.
    
    Path Parameters:
        part_id: Part ID
    
    Response (200 OK):
        {
            "id": "string",
            "name": "string",
            "part_type": "string",
            "sequence": "string",
            "overhang_5prime": "string",
            "overhang_3prime": "string",
            "lab_source": "string",
            "contributor": "string",
            "upload_date": "ISO8601 timestamp",
            "description": "string",
            "length": number
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        404 Not Found: Part not found
    
    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """
    try:
        # Retrieve part
        part = Part.get_by_id(part_id)
        
        if part is None:
            return jsonify({
                'error': f'Part {part_id} not found'
            }), 404
        
        return jsonify(part.to_dict()), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error'
        }), 500


@parts_bp.route('', methods=['POST'])
@require_session
def upload_part():
    """
    Upload a new part to the library.
    
    Supports two methods:
    1. JSON data with manual fields
    2. GenBank file upload (multipart/form-data)
    
    For JSON upload:
        Request Body:
            {
                "name": "string",
                "part_type": "string",
                "sequence": "string",
                "overhang_5prime": "string",
                "overhang_3prime": "string",
                "lab_source": "string",
                "description": "string" (optional)
            }
    
    For GenBank upload:
        Form Data:
            - file: GenBank file (.gb or .genbank)
            - lab_source: Lab source (optional, can be extracted from file)
            - part_type: Override auto-detected part type (optional)
    
    Response (201 Created):
        {
            "part": {
                "id": "string",
                "name": "string",
                "part_type": "string",
                "sequence": "string",
                "overhang_5prime": "string",
                "overhang_3prime": "string",
                "lab_source": "string",
                "contributor": "string",
                "upload_date": "ISO8601 timestamp",
                "description": "string",
                "length": number
            },
            "message": "Part uploaded successfully",
            "source": "genbank" or "manual"
        }
    
    Error Responses:
        400 Bad Request: Invalid or missing fields
        401 Unauthorized: Authentication required
        409 Conflict: Duplicate part exists
    
    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.7
    """
    try:
        # Check if this is a file upload or JSON data
        if request.files and 'file' in request.files:
            # GenBank file upload
            return _handle_genbank_upload()
        else:
            # JSON data upload
            return _handle_json_upload()
        
    except ValidationError as e:
        error_msg = str(e)
        
        # Check if it's a duplicate error
        if 'already exists' in error_msg:
            return jsonify({
                'error': error_msg
            }), 409
        
        # Other validation errors
        return jsonify({
            'error': error_msg
        }), 400
    
    except ValueError as e:
        return jsonify({
            'error': str(e)
        }), 400
    
    except Exception as e:
        return jsonify({
            'error': 'Internal server error'
        }), 500


def _handle_json_upload():
    """Handle manual JSON part upload."""
    # Parse request body
    data = request.get_json(silent=True)
    
    if data is None:
        return jsonify({
            'error': 'Request body must be JSON'
        }), 400
    
    # Extract fields
    name = data.get('name')
    part_type = data.get('part_type')
    sequence = data.get('sequence')
    overhang_5prime = data.get('overhang_5prime')
    overhang_3prime = data.get('overhang_3prime')
    lab_source = data.get('lab_source')
    description = data.get('description')
    
    # Normalize sequence and overhangs (remove whitespace, convert to uppercase)
    if sequence:
        sequence = sequence.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '').upper()
    if overhang_5prime:
        overhang_5prime = overhang_5prime.replace(' ', '').upper()
    if overhang_3prime:
        overhang_3prime = overhang_3prime.replace(' ', '').upper()
    
    # Get contributor from session
    contributor = session.get('username')
    
    # Validate part data
    validate_part_for_upload(
        name=name,
        part_type=part_type,
        sequence=sequence,
        overhang_5prime=overhang_5prime,
        overhang_3prime=overhang_3prime,
        lab_source=lab_source,
        contributor=contributor,
        valid_part_types=Part.VALID_PART_TYPES,
        check_duplicates=True
    )
    
    # Create part
    part = Part.create(
        name=name,
        part_type=part_type,
        sequence=sequence,
        overhang_5prime=overhang_5prime,
        overhang_3prime=overhang_3prime,
        lab_source=lab_source,
        contributor=contributor,
        description=description
    )
    
    return jsonify({
        'part': part.to_dict(),
        'message': 'Part uploaded successfully',
        'source': 'manual'
    }), 201


def _handle_genbank_upload():
    """Handle GenBank file upload for part."""
    from app.services.part_genbank_parser_v2 import parse_part_genbank, PartGenBankError
    
    file = request.files['file']
    
    # Validate file
    if not file or file.filename == '':
        return jsonify({
            'error': 'No file provided'
        }), 400
    
    # Check file extension
    if not file.filename.lower().endswith(('.gb', '.genbank')):
        return jsonify({
            'error': 'File must be a GenBank file (.gb or .genbank)'
        }), 400
    
    # Read file content
    try:
        file_content = file.read().decode('utf-8')
    except UnicodeDecodeError:
        return jsonify({
            'error': 'File must be UTF-8 encoded text'
        }), 400
    
    # Parse GenBank file
    try:
        part_data = parse_part_genbank(file_content)
    except PartGenBankError as e:
        return jsonify({
            'error': f'GenBank parsing error: {str(e)}'
        }), 400
    
    # Get optional form fields (can override auto-detected values)
    lab_source = request.form.get('lab_source', part_data.get('organism', 'Unknown'))
    part_type_override = request.form.get('part_type')
    
    # Use override if provided, otherwise use auto-detected
    part_type = part_type_override if part_type_override else part_data['part_type']
    
    # Get contributor from session
    contributor = session.get('username')
    
    # Prepare comments with intron annotations if present
    comments_text = part_data.get('comments', '')
    if part_data.get('intron_annotations'):
        import json
        intron_json = json.dumps(part_data['intron_annotations'])
        if comments_text:
            comments_text = f"{comments_text}\n\nINTRON_ANNOTATIONS: {intron_json}"
        else:
            comments_text = f"INTRON_ANNOTATIONS: {intron_json}"
    
    # Validate part data
    validate_part_for_upload(
        name=part_data['name'],
        part_type=part_type,
        sequence=part_data['sequence'],
        overhang_5prime=part_data['overhang_5prime'],
        overhang_3prime=part_data['overhang_3prime'],
        lab_source=lab_source,
        contributor=contributor,
        valid_part_types=Part.VALID_PART_TYPES,
        check_duplicates=True
    )
    
    # Create part with additional metadata from plasmid
    part = Part.create(
        name=part_data['name'],
        part_type=part_type,
        sequence=part_data['sequence'],
        overhang_5prime=part_data['overhang_5prime'],
        overhang_3prime=part_data['overhang_3prime'],
        lab_source=lab_source,
        contributor=contributor,
        description=part_data['description'],
        # Plasmid metadata
        antibiotic=part_data.get('antibiotic'),
        size=part_data.get('plasmid_size'),
        ori_ecoli=part_data.get('ori_ecoli'),
        ori_agro=part_data.get('ori_agro'),
        host_strain=part_data.get('host_strain'),
        reference=part_data.get('reference'),
        comments=comments_text
    )
    
    return jsonify({
        'part': part.to_dict(),
        'message': 'Part uploaded successfully from GenBank file',
        'source': 'genbank',
        'detected_type': part_data['part_type'],
        'bsai_sites_found': part_data['bsai_sites_found'],
        'intron_annotations': part_data.get('intron_annotations', [])
    }), 201


@parts_bp.route('/<part_id>', methods=['DELETE'])
@require_session
def delete_part(part_id: str):
    """
    Delete a part.
    
    Path Parameters:
        part_id: Part ID
    
    Response (200 OK):
        {
            "message": "Part deleted successfully"
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied (not owner or system part)
        404 Not Found: Part not found
    
    Requirements: 10.1
    """
    try:
        # Get part
        part = Part.get_by_id(part_id)
        
        if part is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Part {part_id} not found'
            }), 404
        
        # Get current user
        username = session.get('username')
        
        # Check if this is a system part (contributor is 'system')
        if part.contributor == 'system':
            return jsonify({
                'error': 'Forbidden',
                'message': 'Cannot delete system parts (shared library)'
            }), 403
        
        # Check ownership - user can only delete their own parts
        if part.contributor != username:
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied - you can only delete parts you uploaded'
            }), 403
        
        # Delete the part
        part.delete()
        
        return jsonify({
            'message': 'Part deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@parts_bp.route('/<part_id>/compatible', methods=['GET'])
@require_session
def get_compatible_parts(part_id: str):
    """
    Get all parts compatible with the specified part.
    
    Returns parts that can be placed before (their 3' overhang matches
    the target's 5' overhang) and parts that can be placed after
    (their 5' overhang matches the target's 3' overhang).
    
    Path Parameters:
        part_id: Part ID
    
    Response (200 OK):
        {
            "part": {
                "id": "string",
                "name": "string",
                "overhang_5prime": "string",
                "overhang_3prime": "string"
            },
            "compatible": {
                "before": [
                    {
                        "id": "string",
                        "name": "string",
                        "part_type": "string",
                        "overhang_5prime": "string",
                        "overhang_3prime": "string",
                        ...
                    },
                    ...
                ],
                "after": [
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
            },
            "count": {
                "before": number,
                "after": number,
                "total": number
            }
        }
    
    Error Responses:
        401 Unauthorized: Authentication required
        404 Not Found: Part not found
    
    Requirements: 3.1, 3.2
    """
    try:
        # Retrieve target part
        target_part = Part.get_by_id(part_id)
        
        if target_part is None:
            return jsonify({
                'error': f'Part {part_id} not found'
            }), 404
        
        # Get all parts
        all_parts = Part.get_all()
        
        # Find compatible parts
        compatible = find_compatible_parts(target_part, all_parts)
        
        # Convert to dictionaries
        before_data = [part.to_dict() for part in compatible['before']]
        after_data = [part.to_dict() for part in compatible['after']]
        
        return jsonify({
            'part': {
                'id': target_part.id,
                'name': target_part.name,
                'overhang_5prime': target_part.overhang_5prime,
                'overhang_3prime': target_part.overhang_3prime
            },
            'compatible': {
                'before': before_data,
                'after': after_data
            },
            'count': {
                'before': len(before_data),
                'after': len(after_data),
                'total': len(before_data) + len(after_data)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error'
        }), 500


@parts_bp.route('/<part_id>/download/genbank', methods=['GET'])
@require_session
def download_part_genbank(part_id: str):
    """
    Download a part as a GenBank file.
    
    Path Parameters:
        part_id: Part ID
    
    Response (200 OK):
        GenBank file download with Content-Type: text/plain
        Content-Disposition: attachment; filename="{part_name}.gb"
    
    Error Responses:
        401 Unauthorized: Authentication required
        404 Not Found: Part not found
    """
    from flask import make_response
    from app.services.export import export_part_genbank
    
    try:
        # Get part
        part = Part.get_by_id(part_id)
        
        if part is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Part {part_id} not found'
            }), 404
        
        # Generate GenBank content
        genbank_content = export_part_genbank(part_id)
        
        if genbank_content is None:
            return jsonify({
                'error': 'Export failed',
                'message': 'Failed to generate GenBank file'
            }), 500
        
        # Create response with GenBank file
        response = make_response(genbank_content)
        response.headers['Content-Type'] = 'text/plain'
        
        # Sanitize filename
        safe_filename = part.name.replace(' ', '_').replace('/', '_')
        response.headers['Content-Disposition'] = f'attachment; filename="{safe_filename}.gb"'
        
        return response
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@parts_bp.route('/<part_id>', methods=['PUT', 'PATCH'])
@require_session
def update_part(part_id: str):
    """
    Update part metadata.
    
    Path Parameters:
        part_id: Part ID
    
    Request Body (JSON):
        {
            "description": "string (optional)",
            "plasmid_id": "string (optional)",
            "location_80": "string (optional)",
            "location_96_plate": "string (optional)",
            "antibiotic": "string (optional)",
            "level": "string (optional)",
            "unit": "string (optional)",
            "donor_organism": "string (optional)",
            "reference": "string (optional)",
            "host_strain": "string (optional)",
            "sequenced": "string (optional)",
            "comments": "string (optional)",
            "ori_ecoli": "string (optional)",
            "ori_agro": "string (optional)",
            "primer_for_seq": "string (optional)"
        }
    
    Response (200 OK):
        {
            "part": {...},
            "message": "Part updated successfully"
        }
    
    Error Responses:
        400 Bad Request: Invalid data
        401 Unauthorized: Authentication required
        403 Forbidden: Access denied (not the contributor)
        404 Not Found: Part not found
    """
    try:
        # Get part
        part = Part.get_by_id(part_id)
        
        if part is None:
            return jsonify({
                'error': 'Not found',
                'message': f'Part {part_id} not found'
            }), 404
        
        # Check if user is the contributor
        username = session.get('username')
        if part.contributor != username:
            return jsonify({
                'error': 'Forbidden',
                'message': 'You can only edit parts you have uploaded'
            }), 403
        
        # Get update data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'Bad request',
                'message': 'No data provided'
            }), 400
        
        # Update fields using Part.update() method
        try:
            part.update(
                description=data.get('description'),
                plasmid_id=data.get('plasmid_id'),
                location_80=data.get('location_80'),
                location_96_plate=data.get('location_96_plate'),
                antibiotic=data.get('antibiotic'),
                level=data.get('level'),
                unit=data.get('unit'),
                donor_organism=data.get('donor_organism'),
                reference=data.get('reference'),
                host_strain=data.get('host_strain'),
                sequenced=data.get('sequenced'),
                comments=data.get('comments'),
                ori_ecoli=data.get('ori_ecoli'),
                ori_agro=data.get('ori_agro'),
                primer_for_seq=data.get('primer_for_seq')
            )
            
            # Get updated part
            updated_part = Part.get_by_id(part_id)
            
            return jsonify({
                'part': updated_part.to_dict(),
                'message': 'Part updated successfully'
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': 'Update failed',
                'message': str(e)
            }), 400
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500
