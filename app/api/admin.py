"""
Admin API endpoints.

Provides full CRUD management for users, parts, cassettes, backbones,
and plasmids. All endpoints require admin privileges.
"""

from flask import Blueprint, jsonify, request
from app.models.user import User
from app.models.part import Part
from app.models.cassette import Cassette
from app.models.backbone import Backbone
from app.models.final_plasmid import FinalPlasmid
from app.services.authorization import require_auth
from app.models.database import get_connection
import json

admin_bp = Blueprint('admin', __name__)


def require_admin(f):
    """Decorator that requires the authenticated user to be an admin."""
    from functools import wraps

    @wraps(f)
    @require_auth
    def decorated(user, *args, **kwargs):
        if not user.is_admin:
            return jsonify({'error': 'Admin privileges required'}), 403
        return f(user, *args, **kwargs)

    return decorated


# ── Users ──────────────────────────────────────────────────────────────────

@admin_bp.route('/users', methods=['GET'])
@require_admin
def list_users(user):
    users = User.get_all()
    return jsonify({'users': [u.to_dict() for u in users], 'count': len(users)}), 200


@admin_bp.route('/users', methods=['POST'])
@require_admin
def create_user(user):
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    is_admin = bool(data.get('is_admin', False))

    if not username or not password:
        return jsonify({'error': 'username and password are required'}), 400

    try:
        new_user = User.create(username, password, is_admin=is_admin)
        return jsonify({'user': new_user.to_dict(), 'message': 'User created'}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 409


@admin_bp.route('/users/<user_id>', methods=['PUT'])
@require_admin
def update_user(user, user_id):
    target = User.get_by_id(user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin')

    try:
        target.update(
            username=username,
            password=password if password else None,
            is_admin=bool(is_admin) if is_admin is not None else None
        )
        return jsonify({'user': target.to_dict(), 'message': 'User updated'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 409


@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@require_admin
def delete_user(user, user_id):
    if user_id == user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    target = User.get_by_id(user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    target.delete()
    return jsonify({'message': 'User deleted'}), 200


# ── Parts ──────────────────────────────────────────────────────────────────

@admin_bp.route('/parts', methods=['GET'])
@require_admin
def list_parts(user):
    parts = Part.get_all()
    return jsonify({'parts': [p.to_dict() for p in parts], 'count': len(parts)}), 200


@admin_bp.route('/parts/<part_id>', methods=['PUT'])
@require_admin
def update_part(user, part_id):
    part = Part.get_by_id(part_id)
    if not part:
        return jsonify({'error': 'Part not found'}), 404

    data = request.get_json(silent=True) or {}
    try:
        part.update(
            name=data.get('name'),
            part_type=data.get('part_type'),
            sequence=data.get('sequence'),
            overhang_5prime=data.get('overhang_5prime'),
            overhang_3prime=data.get('overhang_3prime'),
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


@admin_bp.route('/parts/<part_id>', methods=['DELETE'])
@require_admin
def delete_part(user, part_id):
    part = Part.get_by_id(part_id)
    if not part:
        return jsonify({'error': 'Part not found'}), 404

    part.delete()
    return jsonify({'message': 'Part deleted'}), 200


# ── Cassettes ──────────────────────────────────────────────────────────────

@admin_bp.route('/cassettes', methods=['GET'])
@require_admin
def list_cassettes(user):
    cassettes = Cassette.get_all()
    return jsonify({'cassettes': [c.to_dict() for c in cassettes], 'count': len(cassettes)}), 200


@admin_bp.route('/cassettes/<cassette_id>', methods=['PUT'])
@require_admin
def update_cassette(user, cassette_id):
    cassette = Cassette.get_by_id(cassette_id)
    if not cassette:
        return jsonify({'error': 'Cassette not found'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name')
    if name:
        try:
            cassette.update_name(name)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

    return jsonify({'cassette': cassette.to_dict(), 'message': 'Cassette updated'}), 200


@admin_bp.route('/cassettes/<cassette_id>', methods=['DELETE'])
@require_admin
def delete_cassette(user, cassette_id):
    cassette = Cassette.get_by_id(cassette_id)
    if not cassette:
        return jsonify({'error': 'Cassette not found'}), 404

    cassette.delete()
    return jsonify({'message': 'Cassette deleted'}), 200


# ── Backbones ──────────────────────────────────────────────────────────────

@admin_bp.route('/backbones', methods=['GET'])
@require_admin
def list_backbones(user):
    backbones = Backbone.get_all()
    return jsonify({'backbones': [b.to_dict() for b in backbones], 'count': len(backbones)}), 200


@admin_bp.route('/backbones/<backbone_id>', methods=['PUT'])
@require_admin
def update_backbone(user, backbone_id):
    backbone = Backbone.get_by_id(backbone_id)
    if not backbone:
        return jsonify({'error': 'Backbone not found'}), 404

    data = request.get_json(silent=True) or {}
    conn = get_connection()
    cursor = conn.cursor()

    fields = ['name', 'description', 'contributor', 'lab_source', 'donor_organism',
              'antibiotic', 'level', 'location_80', 'location_96_plate',
              'ori_ecoli', 'ori_agro', 'reference', 'comments']

    updates = {f: data[f] for f in fields if f in data}
    if not updates:
        conn.close()
        return jsonify({'error': 'No fields to update'}), 400

    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [backbone_id]
    cursor.execute(f"UPDATE backbones SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()

    # Refresh
    backbone = Backbone.get_by_id(backbone_id)
    return jsonify({'backbone': backbone.to_dict(), 'message': 'Backbone updated'}), 200


@admin_bp.route('/backbones/<backbone_id>', methods=['DELETE'])
@require_admin
def delete_backbone(user, backbone_id):
    backbone = Backbone.get_by_id(backbone_id)
    if not backbone:
        return jsonify({'error': 'Backbone not found'}), 404

    backbone.delete()
    return jsonify({'message': 'Backbone deleted'}), 200


# ── Plasmids ───────────────────────────────────────────────────────────────

@admin_bp.route('/plasmids', methods=['GET'])
@require_admin
def list_plasmids(user):
    plasmids = FinalPlasmid.get_all()
    return jsonify({'plasmids': [p.to_dict() for p in plasmids], 'count': len(plasmids)}), 200


@admin_bp.route('/plasmids/<plasmid_id>', methods=['DELETE'])
@require_admin
def delete_plasmid(user, plasmid_id):
    plasmid = FinalPlasmid.get_by_id(plasmid_id)
    if not plasmid:
        return jsonify({'error': 'Plasmid not found'}), 404

    plasmid.delete()
    return jsonify({'message': 'Plasmid deleted'}), 200


# ── Legacy backbone fix endpoint ───────────────────────────────────────────

@admin_bp.route('/fix-backbones', methods=['POST'])
@require_admin
def fix_backbones(user):
    from app.services.restriction_sites import find_moclo_sites, identify_cassette_slots

    backbones = Backbone.get_all()
    if not backbones:
        return jsonify({'message': 'No backbones found', 'total': 0, 'updated': 0, 'failed': 0, 'details': []}), 200

    updated_count = 0
    failed_count = 0
    details = []

    for backbone in backbones:
        try:
            # Determine enzyme: use stored value, or auto-detect
            enzyme = 'BsaI'
            if backbone.restriction_sites and len(backbone.restriction_sites) > 0:
                enzyme = backbone.restriction_sites[0].get('enzyme', 'BsaI')
            else:
                # Auto-detect from sequence
                bsai_sites = find_moclo_sites(backbone.sequence, 'BsaI')
                bpii_sites = find_moclo_sites(backbone.sequence, 'BpiI')
                if len(bpii_sites) >= 2 and len(bsai_sites) < 2:
                    enzyme = 'BpiI'

            sites = find_moclo_sites(backbone.sequence, enzyme)
            if not sites:
                failed_count += 1
                details.append({'name': backbone.name, 'status': 'failed', 'reason': 'No restriction sites found'})
                continue

            slots = identify_cassette_slots(sites)
            if not slots:
                failed_count += 1
                details.append({'name': backbone.name, 'status': 'failed', 'reason': 'No valid cassette slots found'})
                continue

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE backbones SET restriction_sites = ? WHERE id = ?',
                           (json.dumps(sites), backbone.id))
            conn.commit()
            conn.close()

            updated_count += 1
            details.append({
                'name': backbone.name,
                'status': 'updated',
                'sites_count': len(sites),
                'slots_count': len(slots),
            })
        except Exception as e:
            failed_count += 1
            details.append({'name': backbone.name, 'status': 'error', 'reason': str(e)})

    return jsonify({
        'message': f'Processed {len(backbones)} backbones',
        'total': len(backbones),
        'updated': updated_count,
        'failed': failed_count,
        'details': details
    }), 200


@admin_bp.route('/version', methods=['GET'])
@require_auth
def get_version(user):
    """Get current app version."""
    from app.main import APP_VERSION
    return jsonify({'version': APP_VERSION}), 200


@admin_bp.route('/check-update', methods=['GET'])
@require_auth
def check_update(user):
    """
    Check if a newer version is available on GitHub Container Registry.
    Compares current APP_VERSION against latest GitHub release tag.
    """
    import urllib.request
    import json as _json
    from app.main import APP_VERSION
    
    try:
        # Query GitHub API for latest release
        url = 'https://api.github.com/repos/Gardiner-Lab/moclo-library-tool/tags?per_page=5'
        req = urllib.request.Request(url, headers={'User-Agent': 'MoClo-Library-Tool'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            tags = _json.loads(response.read().decode())
        
        if not tags:
            return jsonify({
                'current_version': APP_VERSION,
                'latest_version': None,
                'update_available': False,
                'message': 'Could not determine latest version'
            }), 200
        
        # Get latest tag (sorted by name, tags come newest first from API)
        latest_tag = tags[0]['name'].lstrip('v')
        
        # Compare versions
        def parse_version(v):
            return tuple(int(x) for x in v.split('.'))
        
        current = parse_version(APP_VERSION)
        latest = parse_version(latest_tag)
        update_available = latest > current
        
        return jsonify({
            'current_version': APP_VERSION,
            'latest_version': latest_tag,
            'update_available': update_available,
            'message': f'Update available: v{latest_tag}' if update_available else 'You are up to date',
            'update_instructions': (
                'Run on the host machine:\n'
                'docker-compose -f docker-compose.prod.yml pull\n'
                'docker-compose -f docker-compose.prod.yml up -d\n\n'
                'Or use: ./update-prod.sh'
            ) if update_available else None
        }), 200
        
    except Exception as e:
        return jsonify({
            'current_version': APP_VERSION,
            'latest_version': None,
            'update_available': False,
            'message': f'Could not check for updates: {str(e)}'
        }), 200

# ── Addgene Lookup (Background Job) ────────────────────────────────────────

import threading

# Global state for the background Addgene lookup job
_addgene_job = {
    'running': False,
    'progress': 0,
    'total': 0,
    'updated': 0,
    'failed': 0,
    'skipped': 0,
    'details': [],
    'finished': False,
    'error': None
}
_addgene_lock = threading.Lock()


def _run_addgene_lookup_background():
    """Background thread function to perform Addgene lookups."""
    global _addgene_job
    from app.services.addgene import lookup_addgene_name
    from app.models.parts_database import get_parts_database
    
    try:
        parts = Part.get_all()
        
        generic_descriptions = {
            '', 'synthetic circular dna', 'synthetic circular dna.',
            'synthetic dna construct', 'synthetic dna construct.',
            'none', 'n/a'
        }
        
        with _addgene_lock:
            _addgene_job['total'] = len(parts)
            _addgene_job['progress'] = 0
        
        for i, part in enumerate(parts):
            current_desc = (part.description or '').strip().lower()
            
            with _addgene_lock:
                _addgene_job['progress'] = i + 1
            
            # Skip if already has a meaningful description
            if current_desc and current_desc not in generic_descriptions:
                with _addgene_lock:
                    _addgene_job['skipped'] += 1
                continue
            
            # Try Addgene lookup
            try:
                gene_name = lookup_addgene_name(part.name)
                if gene_name:
                    db = get_parts_database()
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE parts SET description = ? WHERE id = ?",
                            (gene_name, part.id)
                        )
                        conn.commit()
                    with _addgene_lock:
                        _addgene_job['updated'] += 1
                        _addgene_job['details'].append({
                            'name': part.name,
                            'description': gene_name,
                            'status': 'updated'
                        })
                else:
                    with _addgene_lock:
                        _addgene_job['skipped'] += 1
            except Exception as e:
                with _addgene_lock:
                    _addgene_job['failed'] += 1
                    _addgene_job['details'].append({
                        'name': part.name,
                        'status': 'error',
                        'reason': str(e)
                    })
    except Exception as e:
        with _addgene_lock:
            _addgene_job['error'] = str(e)
    finally:
        with _addgene_lock:
            _addgene_job['running'] = False
            _addgene_job['finished'] = True


@admin_bp.route('/addgene-lookup', methods=['POST'])
@require_admin
def batch_addgene_lookup(user):
    """
    Start a background Addgene lookup job.
    
    Returns immediately. Use GET /api/admin/addgene-lookup/status to poll progress.
    """
    global _addgene_job
    
    with _addgene_lock:
        if _addgene_job['running']:
            return jsonify({
                'status': 'already_running',
                'message': 'An Addgene lookup is already in progress.',
                'progress': _addgene_job['progress'],
                'total': _addgene_job['total']
            }), 409
        
        # Reset job state
        _addgene_job = {
            'running': True,
            'progress': 0,
            'total': 0,
            'updated': 0,
            'failed': 0,
            'skipped': 0,
            'details': [],
            'finished': False,
            'error': None
        }
    
    # Start background thread
    thread = threading.Thread(target=_run_addgene_lookup_background, daemon=True)
    thread.start()
    
    return jsonify({
        'status': 'started',
        'message': 'Addgene lookup started in background. Poll /api/admin/addgene-lookup/status for progress.'
    }), 202


@admin_bp.route('/addgene-lookup/status', methods=['GET'])
@require_admin
def addgene_lookup_status(user):
    """
    Get the status of the background Addgene lookup job.
    """
    with _addgene_lock:
        return jsonify({
            'running': _addgene_job['running'],
            'finished': _addgene_job['finished'],
            'progress': _addgene_job['progress'],
            'total': _addgene_job['total'],
            'updated': _addgene_job['updated'],
            'failed': _addgene_job['failed'],
            'skipped': _addgene_job['skipped'],
            'error': _addgene_job['error'],
            'details': _addgene_job['details'][-20:]  # Last 20 results
        }), 200
