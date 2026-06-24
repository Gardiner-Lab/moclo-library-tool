"""
User dashboard API endpoints.

Allows authenticated users to:
- View and update their own account (username, password)
- View, edit, and delete parts they have uploaded
"""

from flask import Blueprint, request, jsonify, session
from app.services.authorization import require_auth
from app.models.part import Part
from app.models.user import User

user_dashboard_bp = Blueprint('user_dashboard', __name__)


# ── Account ────────────────────────────────────────────────────────────────

@user_dashboard_bp.route('/account', methods=['GET'])
@require_auth
def get_account(user):
    """Return the current user's account info."""
    return jsonify({'user': user.to_dict()}), 200


@user_dashboard_bp.route('/account', methods=['PUT'])
@require_auth
def update_account(user):
    """
    Update the current user's username and/or password.

    Request Body:
        {
            "username": "new_username",   (optional)
            "password": "new_password"    (optional)
        }
    """
    data = request.get_json(silent=True) or {}
    new_username = data.get('username', '').strip() or None
    new_password = data.get('password', '').strip() or None

    if not new_username and not new_password:
        return jsonify({'error': 'Nothing to update'}), 400

    try:
        user.update(username=new_username, password=new_password)
    except ValueError as e:
        return jsonify({'error': str(e)}), 409

    # Refresh session username if it changed
    if new_username:
        session['username'] = user.username

    return jsonify({'user': user.to_dict(), 'message': 'Account updated'}), 200


# ── My Parts ───────────────────────────────────────────────────────────────

@user_dashboard_bp.route('/parts', methods=['GET'])
@require_auth
def list_my_parts(user):
    """Return all parts uploaded by the current user."""
    all_parts = Part.get_all()
    my_parts = [p for p in all_parts if p.contributor == user.username]
    return jsonify({'parts': [p.to_dict() for p in my_parts], 'count': len(my_parts)}), 200


@user_dashboard_bp.route('/parts/<part_id>', methods=['PUT'])
@require_auth
def update_my_part(user, part_id):
    """Edit a part the current user uploaded."""
    part = Part.get_by_id(part_id)
    if not part:
        return jsonify({'error': 'Part not found'}), 404
    if part.contributor != user.username:
        return jsonify({'error': 'You can only edit parts you uploaded'}), 403

    data = request.get_json(silent=True) or {}
    try:
        part.update(
            name=data.get('name'),
            part_type=data.get('part_type'),
            lab_source=data.get('lab_source'),
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
            primer_for_seq=data.get('primer_for_seq'),
        )
        return jsonify({'part': part.to_dict(), 'message': 'Part updated'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@user_dashboard_bp.route('/parts/<part_id>', methods=['DELETE'])
@require_auth
def delete_my_part(user, part_id):
    """Delete a part the current user uploaded."""
    part = Part.get_by_id(part_id)
    if not part:
        return jsonify({'error': 'Part not found'}), 404
    if part.contributor != user.username:
        return jsonify({'error': 'You can only delete parts you uploaded'}), 403

    part.delete()
    return jsonify({'message': 'Part deleted'}), 200
