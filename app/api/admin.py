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
        
        import re as _re

        def parse_version(v):
            m = _re.match(r'v?(\d+)\.(\d+)\.(\d+)', str(v or ''))
            return tuple(int(x) for x in m.groups()) if m else None

        # Keep only well-formed semver tags and pick the true maximum.
        semver_tags = [t['name'] for t in tags if parse_version(t.get('name'))]
        semver_tags.sort(key=parse_version)
        latest_tag = semver_tags[-1].lstrip('v') if semver_tags else None

        current = parse_version(APP_VERSION)
        latest = parse_version(latest_tag)

        if not latest or not current:
            return jsonify({
                'current_version': APP_VERSION,
                'latest_version': latest_tag,
                'update_available': False,
                'message': 'Could not determine latest version'
            }), 200

        update_available = latest > current

        repo = 'Gardiner-Lab/moclo-library-tool'
        return jsonify({
            'current_version': APP_VERSION,
            'latest_version': latest_tag,
            'update_available': update_available,
            'ahead_of_release': current > latest,
            'release_notes': f'https://github.com/{repo}/releases/tag/v{latest_tag}',
            'message': (f'Update available: v{latest_tag}' if update_available
                        else ('Running a newer build than the latest release'
                              if current > latest else 'You are up to date')),
            # One-shot manual update on the host (backup + health gate + auto-rollback):
            'manual_command': './update-prod.sh',
            # Hands-off automatic updates: run once, then the container keeps itself current.
            'auto_update_command': (
                'docker compose -f docker-compose.prod.yml '
                '-f docker-compose.watchtower.yml up -d'
            ),
            'update_instructions': (
                'On the host machine run:  ./update-prod.sh\n'
                '(backs up the databases, pulls the new image, health-checks, '
                'and rolls back automatically if the new version is unhealthy)'
            ) if update_available else None
        }), 200
        
    except Exception as e:
        return jsonify({
            'current_version': APP_VERSION,
            'latest_version': None,
            'update_available': False,
            'message': f'Could not check for updates: {str(e)}'
        }), 200


# ── Update Part Descriptions from Features ─────────────────────────────────

@admin_bp.route('/update-descriptions', methods=['POST'])
@require_admin
def update_part_descriptions(user):
    """
    Update all parts' descriptions using their stored .gb feature labels.
    
    Replaces generic descriptions (like "synthetic circular DNA") with
    meaningful feature labels extracted from the GenBank file.
    """
    import json
    from app.models.parts_database import get_parts_database
    
    try:
        parts = Part.get_all()
        
        skip_labels = {'source', 'ori', 'ORI', 'pMB1', 'pBR322ori-F', 'pBRforEco', 'G to A', 'SmR', 'AmpR'}
        interesting_types = {'CDS', 'gene', 'promoter', 'terminator', 'misc_feature', 'regulatory', 'sig_peptide', 'transit_peptide'}
        
        updated = 0
        skipped = 0
        details = []
        
        db = get_parts_database()
        
        for part in parts:
            if not part.features or len(part.features) == 0:
                skipped += 1
                continue
            
            # Build description from feature labels
            labels = []
            seen = set()
            for f in part.features:
                label = f.get('label', '')
                ftype = f.get('type', '')
                if not label or ftype not in interesting_types:
                    continue
                if label in skip_labels or '4bp overhang' in label:
                    continue
                if label not in seen:
                    seen.add(label)
                    labels.append(label)
            
            if not labels:
                skipped += 1
                continue
            
            new_description = ', '.join(labels)
            
            # Update in database
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE parts SET description = ? WHERE id = ?",
                    (new_description, part.id)
                )
                conn.commit()
            
            updated += 1
            details.append({
                'name': part.name,
                'description': new_description
            })
        
        return jsonify({
            'status': 'complete',
            'updated': updated,
            'skipped': skipped,
            'details': details[:50]
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


@admin_bp.route('/reparse-parts', methods=['POST'])
@require_admin
def reparse_parts_from_genbank(user):
    """
    Batch re-upload .gb files to update existing parts with features and descriptions.
    
    Accepts multipart/form-data with multiple .gb files.
    Matches each file to an existing part by name (record ID).
    Updates the part's features and description from the .gb annotations.
    
    Form Data:
        files: One or more .gb files
    """
    from app.services.part_genbank_parser_v2 import _extract_part_features, PartGenBankError
    from Bio import SeqIO
    from io import StringIO
    import json as json_module
    from app.models.parts_database import get_parts_database
    
    if not request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files:
        # Try alternate field name
        files = request.files.getlist('file')
    
    if not files:
        return jsonify({'error': 'No files provided'}), 400
    
    results = {
        'updated': 0,
        'not_found': 0,
        'errors': 0,
        'details': []
    }
    
    skip_labels = {'source', 'ori', 'ORI', 'pMB1', 'pBR322ori-F', 'pBRforEco', 'G to A', 'SmR', 'AmpR'}
    interesting_types = {'CDS', 'gene', 'promoter', 'terminator', 'misc_feature', 'regulatory', 'sig_peptide', 'transit_peptide'}
    
    db = get_parts_database()
    
    for file in files:
        filename = file.filename or ''
        try:
            content = file.read().decode('utf-8')
            handle = StringIO(content)
            record = SeqIO.read(handle, "genbank")
            
            part_name = record.id or record.name
            
            # Extract features
            features = _extract_part_features(record)
            
            # Build description from feature labels
            labels = []
            seen = set()
            for f in features:
                label = f.get('label', '')
                ftype = f.get('type', '')
                if not label or ftype not in interesting_types:
                    continue
                if label in skip_labels or '4bp overhang' in label:
                    continue
                if label not in seen:
                    seen.add(label)
                    labels.append(label)
            
            new_description = ', '.join(labels) if labels else record.description
            
            # Find existing part by name
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM parts WHERE name = ?", (part_name,))
                row = cursor.fetchone()
                
                if row:
                    # Update features and description
                    cursor.execute(
                        "UPDATE parts SET features = ?, description = ? WHERE name = ?",
                        (json_module.dumps(features), new_description, part_name)
                    )
                    conn.commit()
                    results['updated'] += 1
                    results['details'].append({
                        'name': part_name,
                        'status': 'updated',
                        'description': new_description,
                        'feature_count': len(features)
                    })
                else:
                    results['not_found'] += 1
                    results['details'].append({
                        'name': part_name,
                        'status': 'not_found',
                        'file': filename
                    })
        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                'file': filename,
                'status': 'error',
                'reason': str(e)
            })
    
    return jsonify(results), 200


@admin_bp.route('/fetch-genbank-features', methods=['POST'])
@require_admin
def fetch_genbank_features(user):
    """
    Fetch original .gb files from the GitHub MoClo registry for Addgene parts,
    extract features, and update the parts in the database.
    
    Looks up parts matching MoClo naming patterns (pICSL, pICH, pAGM, pAGT)
    and fetches their GenBank files from:
    https://github.com/althonos/moclo/tree/master/moclo-plant/registry/plant/
    """
    try:
        import re
        import urllib.request
        import urllib.error
        import json as json_module
        from io import StringIO
        from Bio import SeqIO
        from app.services.part_genbank_parser_v2 import _extract_part_features
        from app.models.parts_database import get_parts_database
    except ImportError as e:
        return jsonify({'error': f'Missing dependency: {str(e)}'}), 500
    
    GITHUB_BASE = "https://raw.githubusercontent.com/althonos/moclo/master/moclo-plant/registry/plant"
    MOCLO_PATTERN = re.compile(r'^p(I(CSL|CH)|AGM|AGT)\d+$', re.IGNORECASE)
    
    skip_labels = {'source', 'ori', 'ORI', 'pMB1', 'pBR322ori-F', 'pBRforEco', 'G to A', 'SmR', 'AmpR'}
    interesting_types = {'CDS', 'gene', 'promoter', 'terminator', 'misc_feature', 'regulatory', 'sig_peptide', 'transit_peptide'}
    
    # Get all Addgene parts
    parts = Part.get_all()
    addgene_parts = [p for p in parts if MOCLO_PATTERN.match(p.name)]
    
    results = {
        'total': len(addgene_parts),
        'updated': 0,
        'not_found': 0,
        'errors': 0,
        'details': []
    }
    
    db = get_parts_database()
    
    for part in addgene_parts:
        url = f"{GITHUB_BASE}/{part.name}.gb"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'MoClo-Library-Tool/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8')
            
            # Parse the GenBank file
            handle = StringIO(content)
            record = SeqIO.read(handle, "genbank")
            
            # Extract features
            features = _extract_part_features(record)
            
            # Build description from feature labels
            labels = []
            seen = set()
            for f in features:
                label = f.get('label', '')
                ftype = f.get('type', '')
                if not label or ftype not in interesting_types:
                    continue
                if label in skip_labels or '4bp overhang' in label:
                    continue
                if label not in seen:
                    seen.add(label)
                    labels.append(label)
            
            new_description = ', '.join(labels) if labels else 'synthetic circular DNA'
            
            # Update in database
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE parts SET features = ?, description = ? WHERE id = ?",
                    (json_module.dumps(features), new_description, part.id)
                )
                conn.commit()
            
            results['updated'] += 1
            results['details'].append({
                'name': part.name,
                'status': 'updated',
                'description': new_description,
                'feature_count': len(features)
            })
            
        except urllib.error.HTTPError as e:
            if e.code == 404:
                results['not_found'] += 1
                results['details'].append({
                    'name': part.name,
                    'status': 'not_found'
                })
            else:
                results['errors'] += 1
                results['details'].append({
                    'name': part.name,
                    'status': 'error',
                    'reason': f'HTTP {e.code}'
                })
        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                'name': part.name,
                'status': 'error',
                'reason': str(e)
            })
    
    return jsonify(results), 200
