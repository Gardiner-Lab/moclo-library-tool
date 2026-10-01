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
    assemble_level1_guide_cassette,
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


class _SkipL2(Exception):
    """Internal sentinel: skip Level 2 cassette creation (chain invalid)."""
    pass


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


def _load_fillers():
    """
    Load the role-tagged filler parts (dummies, end-linkers) from the library,
    keyed by Level 2 position for the auto-fill assembly.

    Returns {'dummies': {pos: Part}, 'endlinkers': {pos: Part}}.
    """
    from app.services.crispr_design import L2_POSITION_OVERHANGS, reverse_complement
    dummies, endlinkers = {}, {}
    for p in Part.get_all():
        unit = (p.unit or '').lower()
        o5 = (p.overhang_5prime or '').upper()
        o3 = (p.overhang_3prime or '').upper()
        if unit == 'dummy':
            for pos, (b5, b3) in L2_POSITION_OVERHANGS.items():
                if (o5, o3) == (b5, b3):
                    dummies.setdefault(pos, p)
        elif unit == 'endlinker':
            # End-linker closes position N: its 5' matches position N's 3' boundary.
            for pos, (b5, b3) in L2_POSITION_OVERHANGS.items():
                if o5 == b3 and o3 == 'GGGA':
                    endlinkers.setdefault(pos, p)
    return {'dummies': dummies, 'endlinkers': endlinkers}


def _part_brief(part):
    """Compact part summary for the picker UIs."""
    return {
        'id': part.id,
        'name': part.name,
        'part_type': part.part_type,
        'level': part.level,
        'overhang_5prime': part.overhang_5prime,
        'overhang_3prime': part.overhang_3prime,
        'length': len(part.sequence) if part.sequence else 0,
        'description': part.description,
    }


@guide_designer_bp.route('/l1-parts', methods=['GET'])
@require_auth
def search_l1_parts(user):
    """
    Search the parts library for Level 1 parts to use as the Cas nuclease,
    the resistance/selectable-marker unit, or any other Level 1 unit in the
    Level 2 construct.

    Query params:
        search: optional name/id substring filter
        include_all_levels: '1' to not restrict to level == '1' (default off)

    Response: { 'parts': [ {id, name, part_type, level, overhangs, ...}, ... ] }
    """
    try:
        search = (request.args.get('search') or '').strip()
        include_all = request.args.get('include_all_levels') == '1'

        parts = Part.search(search) if search else Part.get_all()

        results = []
        for p in parts:
            # Default to Level 1 parts (the units that assemble into a Level 2),
            # but allow all levels if explicitly requested.
            if not include_all and str(p.level or '') not in ('1', '2'):
                continue
            results.append(_part_brief(p))

        return jsonify({'parts': results, 'count': len(results)}), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


@guide_designer_bp.route('/backbones', methods=['GET'])
@require_auth
def search_backbones(user):
    """
    List available Level 2 acceptor backbones (optionally name-filtered) for the
    final plasmid assembly step.

    Query params:
        search: optional name substring filter

    Response: { 'backbones': [ {id, name, size, slot_count}, ... ] }
    """
    try:
        from app.models.backbone import Backbone
        search = (request.args.get('search') or '').strip().lower()
        backbones = Backbone.get_all()
        results = []
        for b in backbones:
            if search and search not in (b.name or '').lower():
                continue
            results.append({
                'id': b.id,
                'name': b.name,
                'size': getattr(b, 'size', None),
                'slot_count': getattr(b, 'cassette_slots', None),
            })
        return jsonify({'backbones': results, 'count': len(results)}), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


@guide_designer_bp.route('/create-construct', methods=['POST'])
@require_auth
def create_construct(user):
    """
    Create the full CRISPR construct from the designer:
      1. Assemble the Level 1 tRNA-sgRNA guide cassette (from the guides) and save
         it as a Level 1 Part at the chosen acceptor position.
      2. (optional) Create the Level 2 cassette chaining the guide unit + the
         chosen Cas Level 1 part + resistance Level 1 part + any other L1 parts.
      3. (optional) Assemble the Level 2 plasmid by inserting that cassette into
         the chosen Level 2 acceptor backbone.

    Request body:
        {
            "guides": ["ACGT...20bp", ...],
            "promoter": "AtU6-26p",
            "backbone_flavor": "improved",
            "l1_acceptor": "pICH47742",      # guide cassette's L2 position
            "guide_cassette_name": "...",
            "cas_part_id": "...",            # required
            "resistance_part_id": "...",     # required
            "other_part_ids": ["...", ...],  # optional
            "create_l2_cassette": true,
            "l2_cassette_name": "...",
            "create_plasmid": false,
            "l2_backbone_id": "...",         # required if create_plasmid
            "plasmid_name": "..."
        }
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'error': 'Request body must be JSON'}), 400

        guides = data.get('guides')
        if not guides or not isinstance(guides, list):
            return jsonify({'error': 'guides must be a non-empty array'}), 400

        promoter = data.get('promoter', 'TaU3p')
        backbone_flavor = data.get('backbone_flavor', 'improved')
        l1_acceptor = data.get('l1_acceptor', 'pICH47742')
        cas_part_id = data.get('cas_part_id')
        resistance_part_id = data.get('resistance_part_id')
        if not cas_part_id or not resistance_part_id:
            return jsonify({'error': 'Both a Cas Level 1 part and a resistance Level 1 part are required.'}), 400

        other_part_ids = data.get('other_part_ids') or []
        l1_backbone_id = data.get('l1_backbone_id')
        contributor = user.username if hasattr(user, 'username') else 'unknown'

        # ---- 1. Assemble the Level 1 tRNA-sgRNA guide cassette ----
        try:
            l1 = assemble_level1_guide_cassette(
                guides=guides, promoter=promoter,
                backbone_flavor=backbone_flavor, l1_acceptor=l1_acceptor,
            )
        except GuideDesignError as e:
            return jsonify({'error': str(e)}), 400

        guide_cassette_name = (data.get('guide_cassette_name') or '').strip() \
            or f"gRNA_L1_{l1_acceptor}_{len(guides)}guides"

        # Persist the Level 0 breakdown (promoter + each tRNA-sgRNA module) in the
        # part comments so it propagates into the Level 2 cassette / plasmid
        # assembly information, exactly like a manually built Level 1 cassette.
        import json as _json
        guide_comments = f"SUBPARTS: {_json.dumps(l1.get('sub_parts', []))}"

        guide_part = Part.create(
            name=guide_cassette_name,
            part_type='Coding',
            sequence=l1['sequence'],
            overhang_5prime=l1['overhang_5prime'],
            overhang_3prime=l1['overhang_3prime'],
            lab_source=data.get('lab_source') or 'Unknown',
            contributor=contributor,
            description=f"Level 1 tRNA-sgRNA guide cassette ({len(guides)} guides, {promoter}, {backbone_flavor}; acceptor {l1_acceptor})",
            level='1',
            unit='gRNA-array',
            plasmid_id=l1_acceptor,
            comments=guide_comments,
            features=l1.get('features'),
        )

        result = {
            'guide_cassette_part': {
                'id': guide_part.id,
                'name': guide_part.name,
                'level': '1',
                'position': l1['position'],
                'overhang_5prime': l1['overhang_5prime'],
                'overhang_3prime': l1['overhang_3prime'],
                'length': l1['length'],
            },
            'l1_plasmid': None,
            'l2_cassette': None,
            'plasmid': None,
            # Per-level reaction inputs so the frontend can build the Level 0 /
            # Level 1 / Level 2 reaction-calculator fragment lists.
            #   level0_fragments: the Level 0 tRNA-sgRNA modules (promoter +
            #     guide modules) — the inserts cloned (via BpiI) with their
            #     oligos into the Level 0 position vectors.
            'level0_fragments': l1.get('sub_parts') or [],
            'l1_acceptor_backbone': None,  # set below when a Level 1 plasmid is made
            'messages': [f"Created Level 1 guide cassette part '{guide_part.name}'."],
        }

        # ---- 1b. Optionally assemble the Level 1 plasmid into a selected
        # Level 1 acceptor backbone, exactly like the manual assembly flow. This
        # produces a real Level 1 FinalPlasmid plus an auto-created '<name>_L1'
        # Level 1 Part (with the correct BpiI fusion overhangs read back from the
        # assembled sequence). That _L1 part becomes the guide unit used in the
        # Level 2 build. If no Level 1 backbone is selected we fall back to the
        # bare guide_part (previous behaviour).
        guide_unit = guide_part
        if l1_backbone_id:
            from app.models.backbone import Backbone
            from app.services.plasmid_assembly import assemble_level1_guide_plasmid, AssemblyError as PAErr
            from app.services.crispr_design import L2_POSITION_OVERHANGS

            l1_backbone = Backbone.get_by_id(l1_backbone_id)
            if l1_backbone is None:
                return jsonify({'error': 'Level 1 acceptor backbone not found.'}), 404

            # The guide cassette's Level 2 position was set by the chosen L1
            # acceptor dropdown (l1['position']); the resulting Level 1 unit
            # presents that position's canonical BpiI fusion overhangs.
            position = l1['position']
            o5, o3 = L2_POSITION_OVERHANGS[position]

            l1_plasmid_name = (data.get('l1_plasmid_name') or '').strip() or guide_cassette_name
            try:
                l1_plasmid = assemble_level1_guide_plasmid(
                    backbone=l1_backbone,
                    array_sequence=l1['sequence'],
                    position=position,
                    name=l1_plasmid_name,
                    owner_id=user.id,
                    l2_overhang_5prime=o5,
                    l2_overhang_3prime=o3,
                    sub_parts=l1.get('sub_parts'),
                    guide_cassette_name=guide_cassette_name,
                    array_features=l1.get('features'),
                )
                created_part_id = (l1_plasmid.metadata or {}).get('created_part_id')
                l1_unit_part = Part.get_by_id(created_part_id) if created_part_id else None

                result['l1_plasmid'] = {
                    'id': l1_plasmid.id, 'name': l1_plasmid.name,
                    'length': len(l1_plasmid.assembled_sequence),
                    'backbone_name': l1_backbone.name,
                    'backbone_size': getattr(l1_backbone, 'size', None),
                    'l1_part_id': l1_unit_part.id if l1_unit_part else None,
                    'l1_part_name': l1_unit_part.name if l1_unit_part else None,
                }
                # The Level 1 reaction uses this acceptor as the vector.
                result['l1_acceptor_backbone'] = {
                    'name': l1_backbone.name,
                    'size': getattr(l1_backbone, 'size', None),
                }
                result['messages'].append(
                    f"Assembled Level 1 plasmid '{l1_plasmid.name}' into backbone '{l1_backbone.name}' "
                    f"(position {position})."
                )
                if l1_unit_part is not None:
                    # Use the real Level 1 unit (named '<name>_L1') for the L2 build.
                    guide_unit = l1_unit_part
                    result['messages'].append(
                        f"Created Level 1 part '{l1_unit_part.name}' for Level 2 assembly."
                    )
            except PAErr as e:
                result['messages'].append(
                    f"Level 1 plasmid not assembled — {str(e)}. "
                    f"Using the unbundled guide cassette part for Level 2 instead."
                )

        # ---- 2. Optionally create the Level 2 cassette ----
        if data.get('create_l2_cassette'):
            from app.services.assembly import create_cassette, validate_assembly

            cas_part = Part.get_by_id(cas_part_id)
            resistance_part = Part.get_by_id(resistance_part_id)
            if cas_part is None or resistance_part is None:
                return jsonify({'error': 'Cas or resistance part not found.'}), 404

            others = []
            for pid in other_part_ids:
                op = Part.get_by_id(pid)
                if op is None:
                    return jsonify({'error': f'Other part {pid} not found.'}), 404
                others.append(op)

            # Position-aware Level 2 build: map each selected part to its L2
            # position, auto-fill internal gaps with dummies, and close with the
            # matching end-linker so the chain spans TGCC -> GGGA (fits the
            # universal acceptor).
            from app.services.crispr_design import plan_level2_components
            fillers = _load_fillers()
            selected = [guide_unit, cas_part, resistance_part] + others
            plan2 = plan_level2_components(selected, fillers)

            l2_name = (data.get('l2_cassette_name') or '').strip() or f"L2_{guide_cassette_name}"

            if plan2['error']:
                result['messages'].append(f"Level 2 cassette not created — {plan2['error']}")
            else:
                components = plan2['ordered']
                result['l2_layout'] = plan2['layout']
                for w in plan2['warnings']:
                    result['messages'].append(w)
                # Validate the fully-filled chain for a clear error.
                v = validate_assembly(components)
                if not v['valid']:
                    result['messages'].append(
                        f"Level 2 cassette not created — components do not form a valid chain: {v['error']}"
                    )
                try:
                    if not v['valid']:
                        raise _SkipL2()
                    l2 = create_cassette(name=l2_name, owner_id=user.id, parts=components)
                    result['l2_cassette'] = {
                        'id': l2.id, 'name': l2.name, 'level': l2.level,
                        'length': len(l2.assembled_sequence),
                        'part_count': len(l2.part_ids),
                    }
                    result['messages'].append(f"Created Level 2 cassette '{l2.name}'.")

                    # ---- 3. Optionally create the Level 2 plasmid ----
                    if data.get('create_plasmid'):
                        l2_backbone_id = data.get('l2_backbone_id')
                        if not l2_backbone_id:
                            result['messages'].append('Plasmid not created — no Level 2 backbone selected.')
                        else:
                            from app.models.backbone import Backbone
                            from app.services.plasmid_assembly import assemble_plasmid, AssemblyError as PAErr
                            backbone = Backbone.get_by_id(l2_backbone_id)
                            if backbone is None:
                                result['messages'].append('Plasmid not created — backbone not found.')
                            else:
                                try:
                                    plasmid = assemble_plasmid(
                                        backbone=backbone, cassettes=[l2],
                                        name=(data.get('plasmid_name') or '').strip() or f"{l2_name}_plasmid",
                                        owner_id=user.id,
                                    )
                                    result['plasmid'] = {
                                        'id': plasmid.id, 'name': plasmid.name,
                                        'length': len(plasmid.assembled_sequence),
                                        'backbone_name': backbone.name,
                                        'backbone_size': getattr(backbone, 'size', None),
                                    }
                                    result['messages'].append(f"Created Level 2 plasmid '{plasmid.name}'.")
                                except PAErr as e:
                                    result['messages'].append(f"Plasmid not created — {str(e)}")
                except _SkipL2:
                    pass  # invalid chain already reported above
                except Exception as e:  # noqa: BLE001
                    result['messages'].append(f"Level 2 cassette not created — {str(e)}")

        return jsonify(result), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500
