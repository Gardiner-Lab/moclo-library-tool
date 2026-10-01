"""
API endpoints for the CRISPR/Cas guide construct designer.

Given one or more guide (protospacer) sequences plus a chosen Pol III promoter,
sgRNA backbone flavour and Level 1 acceptor, returns a complete Golden Gate
cloning strategy (Levels -1, 0, 1, 2) based on the Hahn/Nekrasov (2020) plant
genome-editing MoClo toolkit.
"""

from flask import Blueprint, request, jsonify

from app.services.authorization import require_auth
from app.services.crispr_design import (
    design_trna_sgrna_strategy,
    design_oligos,
    validate_guide,
    build_level0_part_payload,
    GuideDesignError,
    POL3_PROMOTERS,
    L1_ACCEPTORS,
    TRNA_OVERHANG_5,
    TRNA_OVERHANG_3,
    TRNA_GUIDE_LEN,
    MAX_TRNA_GUIDES,
)
from app.models.part import Part

guide_designer_bp = Blueprint('guide_designer', __name__)


@guide_designer_bp.route('/options', methods=['GET'])
@require_auth
def get_options(user):
    """
    Return the selectable options for the designer UI: Pol III promoters,
    Level 1 acceptors and constant design parameters.
    """
    try:
        promoters = [
            {
                'key': key,
                'description': info['description'],
                'start_nt': info['start_nt'],
                'host': info['host'],
                'vector': info['vector'],
            }
            for key, info in POL3_PROMOTERS.items()
        ]
        acceptors = [
            {'vector': v, 'position': info['position']}
            for v, info in sorted(L1_ACCEPTORS.items(), key=lambda kv: kv[1]['position'])
        ]
        return jsonify({
            'promoters': promoters,
            'l1_acceptors': acceptors,
            'backbone_flavors': ['improved', 'classic'],
            'guide_length': TRNA_GUIDE_LEN,
            'max_guides': MAX_TRNA_GUIDES,
            'overhang_5prime': TRNA_OVERHANG_5,
            'overhang_3prime': TRNA_OVERHANG_3,
        }), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


@guide_designer_bp.route('/validate', methods=['POST'])
@require_auth
def validate(user):
    """
    Validate a single guide sequence without designing oligos.

    Request body: {"guide": "ACGT...", "guide_length": 20}
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'error': 'Request body must be JSON'}), 400
        guide = data.get('guide')
        if not guide:
            return jsonify({'error': 'guide is required'}), 400
        guide_len = data.get('guide_length', TRNA_GUIDE_LEN)
        try:
            normalized = validate_guide(guide, int(guide_len))
        except GuideDesignError as e:
            return jsonify({'valid': False, 'error': str(e)}), 200
        return jsonify({'valid': True, 'guide': normalized}), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


@guide_designer_bp.route('/design', methods=['POST'])
@require_auth
def design(user):
    """
    Generate the full tRNA-sgRNA cloning strategy for a set of guides.

    Request body:
        {
            "guides": ["ACGT...20bp", ...],   # 1-6, in array order
            "promoter": "AtU6-26p",           # optional, default TaU3p
            "backbone_flavor": "improved",    # optional, 'improved' or 'classic'
            "l1_acceptor": "pICH47742"        # optional, default pICH47742
        }

    Response (200): the structured cloning plan (see crispr_design service).
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'error': 'Request body must be JSON'}), 400

        guides = data.get('guides')
        if not guides or not isinstance(guides, list):
            return jsonify({'error': 'guides must be a non-empty array of sequences'}), 400

        promoter = data.get('promoter', 'TaU3p')
        backbone_flavor = data.get('backbone_flavor', 'improved')
        l1_acceptor = data.get('l1_acceptor', 'pICH47742')

        try:
            plan = design_trna_sgrna_strategy(
                guides=guides,
                promoter=promoter,
                backbone_flavor=backbone_flavor,
                l1_acceptor=l1_acceptor,
            )
        except GuideDesignError as e:
            return jsonify({'error': str(e)}), 400

        return jsonify({'plan': plan}), 200

    except Exception as e:
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


@guide_designer_bp.route('/create-parts', methods=['POST'])
@require_auth
def create_parts(user):
    """
    Assemble the full Level 0 guide-cassette module(s) and save each as a Part.

    Request body:
        {
            "promoter": "AtU6-26p",
            "backbone_flavor": "improved",
            "guides": [
                {"guide": "ACGT...20bp", "name": "AtPDS_g1_L0",
                 "lab_source": "...", "description": "..."},
                ...
            ]
        }

    The array position of each guide is its index in the list (1-based). The
    stored Part sequence is the FULL assembled Level 0 module (real toolkit
    vector with the guide spliced in), with the MoClo cloning strategy and oligo
    annealing protocol saved in the part's comments.

    Response (201): { "parts": [ {part summary}, ... ], "message": "..." }
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'error': 'Request body must be JSON'}), 400

        promoter = data.get('promoter', 'TaU3p')
        backbone_flavor = data.get('backbone_flavor', 'improved')
        guides = data.get('guides')

        if not guides or not isinstance(guides, list):
            return jsonify({'error': 'guides must be a non-empty array'}), 400
        if len(guides) > MAX_TRNA_GUIDES:
            return jsonify({
                'error': f'The tRNA-sgRNA system supports up to {MAX_TRNA_GUIDES} guides per Level 1 unit.'
            }), 400

        contributor = user.username if hasattr(user, 'username') else data.get('contributor', 'unknown')

        # Build all payloads first (validate everything before creating any parts)
        payloads = []
        for i, entry in enumerate(guides):
            if not isinstance(entry, dict):
                return jsonify({'error': f'guides[{i}] must be an object with guide/name'}), 400
            guide_seq = (entry.get('guide') or '').strip()
            name = (entry.get('name') or '').strip()
            if not guide_seq:
                return jsonify({'error': f'guides[{i}].guide is required'}), 400
            if not name:
                return jsonify({'error': f'guides[{i}].name is required'}), 400
            try:
                payload = build_level0_part_payload(
                    guide=guide_seq,
                    name=name,
                    position=i + 1,
                    promoter=promoter,
                    backbone_flavor=backbone_flavor,
                    lab_source=entry.get('lab_source', ''),
                    description=entry.get('description', ''),
                )
            except GuideDesignError as e:
                return jsonify({'error': f'guides[{i}] ({name or guide_seq}): {str(e)}'}), 400
            payloads.append(payload)

        # Create the parts
        created = []
        for p in payloads:
            part = Part.create(
                name=p['name'],
                part_type=p['part_type'],
                sequence=p['sequence'],
                overhang_5prime=p['overhang_5prime'],
                overhang_3prime=p['overhang_3prime'],
                lab_source=p.get('lab_source') or 'Unknown',
                contributor=contributor,
                description=p['description'],
                level=p['level'],
                unit=p['unit'],
                comments=p['comments'],
                plasmid_id=p.get('plasmid_id'),
                features=p.get('features'),
            )
            created.append({
                'id': part.id,
                'name': part.name,
                'vector': p['vector'],
                'position': p['position'],
                'guide': p['guide'],
                'length': p['module_length'],
                'overhang_5prime': p['overhang_5prime'],
                'overhang_3prime': p['overhang_3prime'],
                'forward_oligo': p['oligos']['forward_oligo'],
                'reverse_oligo': p['oligos']['reverse_oligo'],
            })

        return jsonify({
            'parts': created,
            'message': f'Created {len(created)} Level 0 guide cassette part(s).'
        }), 201

    except ValueError as e:
        # Part.create validation errors (e.g. duplicate name)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500
