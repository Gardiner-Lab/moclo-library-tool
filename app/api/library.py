"""
Who sees the MoClo library, inside Trellis Tools (app/services/library_access.py).

    GET    /api/library/sharing     the chair groups, which share with which, and
                                    which this person may manage
    POST   /api/library/sharing     {from_group, to_group}: from_group's library is
                                    seen, read-only, by to_group
    DELETE /api/library/sharing     {from_group, to_group}: stop sharing
    PUT    /api/library/reference   {kind, id, reference}: an administrator marks
                                    a part, backbone or plasmid as reference
                                    (seen by every lab), or un-marks it

Administrators share any chair group's library; a lab admin shares their own
chair group's. A part or backbone an administrator adds is marked reference as it
is added (library_access.mark_if_administrators); it can be un-marked here.
"""

from flask import Blueprint, jsonify, request

from app.models.backbone import Backbone
from app.models.final_plasmid import FinalPlasmid
from app.models.part import Part
from app.services import library_access
from app.services.authorization import require_auth

library_bp = Blueprint('library', __name__)


def _sharing(user):
    groups = library_access.chair_groups()
    mine = library_access.groups_of(user.username)
    shares = library_access.shares()
    if library_access.in_demo(user.username):
        # The teaching demo is shown its own chair group only, not the real ones.
        groups = {gid: name for gid, name in groups.items() if gid in mine}
        shares = [s for s in shares if s.get('from_group') in mine and s.get('to_group') in mine]
    return {
        'enabled': library_access.enabled(),
        'groups': [{'id': gid, 'name': name, 'mine': gid in mine,
                    'manage': library_access.can_manage_shares(user, gid)}
                   for gid, name in sorted(groups.items(), key=lambda g: (g[1] or '').casefold())],
        'shares': shares,
    }


@library_bp.route('/sharing', methods=['GET'])
@require_auth
def get_sharing(user):
    return jsonify(_sharing(user)), 200


def _pair():
    data = request.get_json(silent=True) or {}
    return str(data.get('from_group') or '').strip(), str(data.get('to_group') or '').strip()


@library_bp.route('/sharing', methods=['POST'])
@require_auth
def add_sharing(user):
    from_group, to_group = _pair()
    if not from_group or not to_group:
        return jsonify({'error': 'Choose the chair group that shares and the one it shares with'}), 400
    if not library_access.can_manage_shares(user, from_group):
        return jsonify({'error': "Only an administrator or a lab admin of one of its labs shares a chair group's library"}), 403
    if library_access.in_demo(user.username):
        return jsonify({'error': "The demo's library is not shared with other chair groups"}), 403
    try:
        library_access.add_share(from_group, to_group, user.username)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify(_sharing(user)), 200


@library_bp.route('/sharing', methods=['DELETE'])
@require_auth
def remove_sharing(user):
    from_group, to_group = _pair()
    if not library_access.can_manage_shares(user, from_group):
        return jsonify({'error': "Only an administrator or a lab admin of one of its labs changes a chair group's sharing"}), 403
    library_access.remove_share(from_group, to_group)
    return jsonify(_sharing(user)), 200


_LOADERS = {'part': Part.get_by_id, 'backbone': Backbone.get_by_id, 'plasmid': FinalPlasmid.get_by_id}


@library_bp.route('/reference', methods=['PUT'])
@require_auth
def set_reference(user):
    if not getattr(user, 'is_admin', False):
        return jsonify({'error': 'Only an administrator marks reference records'}), 403
    data = request.get_json(silent=True) or {}
    kind, record_id = data.get('kind'), str(data.get('id') or '')
    if kind not in _LOADERS:
        return jsonify({'error': 'kind must be part, backbone or plasmid'}), 400
    if _LOADERS[kind](record_id) is None:
        return jsonify({'error': f'{kind.capitalize()} {record_id} not found'}), 404
    library_access.set_reference(kind, record_id, bool(data.get('reference')), user.username)
    return jsonify({'kind': kind, 'id': record_id, 'reference': bool(data.get('reference'))}), 200
