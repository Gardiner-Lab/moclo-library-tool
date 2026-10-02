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


def _existing_part_names():
    """Set of all current part names (lower-cased) for uniqueness checks."""
    try:
        return {(p.name or '').strip().lower() for p in Part.get_all()}
    except Exception:  # noqa: BLE001
        return set()


def _unique_part_name(base, taken):
    """
    Return a unique part name derived from `base`, appending _2, _3, ... until it
    is not in `taken` (a mutable set of lower-cased names, updated in place).
    `base` is used as-is when free. Keeps user intent while guaranteeing no
    duplicate names are created in one construct run.
    """
    base = (base or 'part').strip() or 'part'
    candidate = base
    n = 2
    while candidate.strip().lower() in taken:
        candidate = f"{base}_{n}"
        n += 1
    taken.add(candidate.strip().lower())
    return candidate


def _resolve_l1_acceptor_backbone(l1_acceptor):
    """
    Find the uploaded Level 1 acceptor backbone that matches the vector chosen in
    the top-of-page dropdown (e.g. 'pICH47742'). Match on plasmid_id first, then
    fall back to a name containing the vector id. Returns a Backbone or None.
    """
    from app.models.backbone import Backbone
    if not l1_acceptor:
        return None
    want = l1_acceptor.strip().lower()
    backbones = Backbone.get_all()
    # Exact plasmid_id match.
    for b in backbones:
        if (getattr(b, 'plasmid_id', '') or '').strip().lower() == want:
            return b
    # Fallback: name contains the vector id.
    for b in backbones:
        if want in (b.name or '').strip().lower():
            return b
    return None


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


def _classify_problems(result, l1_acceptor=None, create_plasmid=False):
    """
    Split the construct messages into user-facing problems (with actionable
    guidance) vs. plain informational/success notes, and set an overall
    `complete` flag so the UI can tell the user exactly what failed and how to
    fix it.

    Mutates `result` in place, adding:
      - result['problems']: list of {message, guidance, level} for anything that
        prevented a record from being created.
      - result['info']: the remaining (success/neutral) messages.
      - result['complete']: True when every requested record was produced.
    """
    failure_markers = (
        'not created', 'not assembled', 'not found', 'does not form a valid',
        'no uploaded level 1 acceptor', 'no level 2 backbone', 'failed',
    )

    def guidance_for(msg):
        low = msg.lower()
        if 'level 1 acceptor' in low and ('no uploaded' in low or 'matches' in low):
            pid = l1_acceptor or 'the chosen acceptor'
            return (f"Upload the Level 1 acceptor backbone (plasmid_id "
                    f"{pid}) under Backbones, then recreate the construct. "
                    f"The acceptor you pick at the top of the page must exist "
                    f"as an uploaded backbone.")
        if 'no level 2 backbone selected' in low:
            return ("Pick a Level 2 acceptor backbone in the construct panel "
                    "before creating the construct.")
        if 'backbone not found' in low:
            return ("The selected Level 2 backbone no longer exists — re-select "
                    "a Level 2 acceptor and try again.")
        if 'map to level 2 position' in low or 'two parts map' in low:
            return ("Two parts want the same Level 2 position. Pick a Level 1 "
                    "acceptor whose position differs from your Cas/resistance/"
                    "other parts, or remove the clashing part.")
        if 'does not form a valid chain' in low or 'valid chain' in low:
            return ("The parts' overhangs don't join end-to-end. Check that each "
                    "selected part maps to a distinct Level 2 position and that "
                    "the Cas/resistance parts use standard MoClo overhangs.")
        if 'level 0 module' in low:
            return ("Check the guide sequence (length/characters) and the "
                    "selected promoter and backbone flavor.")
        if 'level 2 cassette' in low:
            return ("Review the selected Cas, resistance and other Level 1 "
                    "parts — one of them could not be placed into the cassette.")
        if 'level 2 plasmid' in low:
            return ("The Level 2 cassette could not be ligated into the chosen "
                    "acceptor — verify the acceptor's overhangs are compatible.")
        if 'level 1 plasmid' in low:
            return ("The Level 1 guide plasmid could not be assembled into its "
                    "acceptor — verify the acceptor backbone is correct.")
        return ("Review the selected parts and backbones, then recreate the "
                "construct.")

    problems = []
    info = []
    for msg in result.get('messages', []):
        low = msg.lower()
        if any(m in low for m in failure_markers):
            problems.append({
                'message': msg,
                'guidance': guidance_for(msg),
                'level': 'error',
            })
        else:
            info.append(msg)

    # Complete = every requested target exists.
    complete = bool(result.get('l1_plasmid')) and bool(result.get('l2_cassette'))
    if create_plasmid:
        complete = complete and bool(result.get('plasmid'))
    # A hard failure anywhere means not complete.
    if problems:
        complete = False

    result['problems'] = problems
    result['info'] = info
    result['complete'] = complete


@guide_designer_bp.route('/create-construct', methods=['POST'])
@require_auth
def create_construct(user):
    """
    Create the full CRISPR construct from the designer, with complete lineage so
    every assembled record can be traced back to its parts:

      1. Persist each Level 0 tRNA-sgRNA guide-module Part (guide spliced into the
         real toolkit vector).
      2. Assemble the Level 1 guide plasmid into the Level 1 acceptor backbone
         that matches the acceptor chosen at the top of the page (auto-resolved;
         no separate picker). Yields a Level 1 FinalPlasmid + a Level 1 unit Part.
      3. Build the Level 2 cassette (guide unit + Cas + resistance + others,
         auto-filled with dummies + end-linker).
      4. (optional) Assemble the Level 2 plasmid into the chosen Level 2 acceptor.

    Minimal input: a single `construct_name` drives collision-safe unique names
    for every child record; individual names can be overridden via `names`.
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
        contributor = user.username if hasattr(user, 'username') else 'unknown'
        names = data.get('names') or {}
        base_name = (data.get('construct_name') or '').strip() or f"CRISPR_{l1_acceptor}_{len(guides)}g"
        lab_source = data.get('lab_source') or 'CRISPR Designer'

        # Running set of names so every record created in this run is unique.
        taken = _existing_part_names()

        from app.models.backbone import Backbone
        from app.services.plasmid_assembly import (
            assemble_level1_guide_plasmid, assemble_plasmid, AssemblyError as PAErr,
        )
        from app.services.crispr_design import (
            L2_POSITION_OVERHANGS, build_level0_part_payload, plan_level2_components,
        )
        from app.services.assembly import create_cassette, validate_assembly
        import json as _json

        result = {
            'level0_parts': [], 'guide_cassette_part': None, 'l1_plasmid': None,
            'l2_cassette': None, 'plasmid': None, 'level0_fragments': [],
            'l1_acceptor_backbone': None, 'messages': [],
        }

        # ---- 0. Assemble the Level 1 guide-cassette sequence ----
        try:
            l1 = assemble_level1_guide_cassette(
                guides=guides, promoter=promoter,
                backbone_flavor=backbone_flavor, l1_acceptor=l1_acceptor,
            )
        except GuideDesignError as e:
            return jsonify({'error': str(e)}), 400
        result['level0_fragments'] = l1.get('sub_parts') or []
        position = l1['position']

        # ---- 1. Persist the Level 0 guide-module Parts (provenance) ----
        level0_name_overrides = names.get('level0') or []
        for i, g in enumerate(guides):
            override = level0_name_overrides[i] if i < len(level0_name_overrides) else None
            l0_name = _unique_part_name(
                (override or '').strip() or f"{base_name}_L0_pos{i + 1}", taken)
            try:
                payload = build_level0_part_payload(
                    guide=g, name=l0_name, position=i + 1,
                    promoter=promoter, backbone_flavor=backbone_flavor,
                    lab_source=lab_source,
                    description=f"Level 0 tRNA-sgRNA guide module for {base_name} (guide {i + 1})",
                )
                p0 = Part.create(
                    name=payload['name'], part_type=payload['part_type'],
                    sequence=payload['sequence'],
                    overhang_5prime=payload['overhang_5prime'],
                    overhang_3prime=payload['overhang_3prime'],
                    lab_source=payload.get('lab_source') or lab_source,
                    contributor=contributor, description=payload['description'],
                    level=payload['level'], unit=payload['unit'],
                    comments=payload['comments'], plasmid_id=payload.get('plasmid_id'),
                    features=payload.get('features'),
                )
                result['level0_parts'].append({
                    'id': p0.id, 'name': p0.name, 'vector': payload['vector'],
                    'position': payload['position'], 'guide': payload['guide'],
                    'length': payload['module_length'],
                })
            except (GuideDesignError, ValueError) as e:
                result['messages'].append(f"Level 0 module {i + 1} not created — {str(e)}")
        if result['level0_parts']:
            result['messages'].append(
                f"Created {len(result['level0_parts'])} Level 0 guide module part(s).")

        # ---- 2. Assemble the Level 1 guide plasmid into the matching acceptor ----
        # Auto-resolve the uploaded Level 1 acceptor backbone from the acceptor
        # vector chosen at the top of the page (no separate picker needed).
        l1_backbone = _resolve_l1_acceptor_backbone(l1_acceptor)
        guide_unit = None
        if l1_backbone is None:
            result['messages'].append(
                f"No uploaded Level 1 acceptor backbone matches '{l1_acceptor}'. "
                f"Upload it (plasmid_id {l1_acceptor}) to assemble the Level 1 plasmid.")
            gp_name = _unique_part_name(names.get('l1_cassette') or f"{base_name}_L1_cassette", taken)
            guide_unit = Part.create(
                name=gp_name, part_type='Coding', sequence=l1['sequence'],
                overhang_5prime=l1['overhang_5prime'], overhang_3prime=l1['overhang_3prime'],
                lab_source=lab_source, contributor=contributor,
                description=f"Level 1 tRNA-sgRNA guide cassette ({len(guides)} guides; acceptor {l1_acceptor})",
                level='1', unit='gRNA-array', plasmid_id=l1_acceptor,
                comments=f"SUBPARTS: {_json.dumps(l1.get('sub_parts', []))}",
                features=l1.get('features'),
            )
            result['guide_cassette_part'] = {
                'id': guide_unit.id, 'name': guide_unit.name, 'level': '1',
                'position': position, 'length': l1['length'],
            }
        else:
            o5, o3 = L2_POSITION_OVERHANGS[position]
            # assemble_level1_guide_plasmid creates a Level 1 unit PART named
            # "<l1_plasmid_name>_L1"; pick an l1_plasmid_name whose _L1 derived
            # part name is unique, and reserve both.
            _base_l1 = (names.get('l1_plasmid') or f"{base_name}_L1").strip() or f"{base_name}_L1"
            l1_plasmid_name = _base_l1
            _n = 2
            while (f"{l1_plasmid_name}_L1".strip().lower() in taken
                   or l1_plasmid_name.strip().lower() in taken):
                l1_plasmid_name = f"{_base_l1}_{_n}"
                _n += 1
            taken.add(l1_plasmid_name.strip().lower())
            taken.add(f"{l1_plasmid_name}_L1".strip().lower())
            try:
                l1_plasmid = assemble_level1_guide_plasmid(
                    backbone=l1_backbone, array_sequence=l1['sequence'],
                    position=position, name=l1_plasmid_name, owner_id=user.id,
                    l2_overhang_5prime=o5, l2_overhang_3prime=o3,
                    sub_parts=l1.get('sub_parts'), guide_cassette_name=l1_plasmid_name,
                    array_features=l1.get('features'),
                )
                created_part_id = (l1_plasmid.metadata or {}).get('created_part_id')
                l1_unit_part = Part.get_by_id(created_part_id) if created_part_id else None
                guide_unit = l1_unit_part
                result['l1_plasmid'] = {
                    'id': l1_plasmid.id, 'name': l1_plasmid.name,
                    'length': len(l1_plasmid.assembled_sequence),
                    'backbone_name': l1_backbone.name,
                    'backbone_size': getattr(l1_backbone, 'size', None),
                    'l1_part_id': l1_unit_part.id if l1_unit_part else None,
                    'l1_part_name': l1_unit_part.name if l1_unit_part else None,
                }
                result['l1_acceptor_backbone'] = {
                    'name': l1_backbone.name, 'size': getattr(l1_backbone, 'size', None),
                }
                result['messages'].append(
                    f"Assembled Level 1 plasmid '{l1_plasmid.name}' into '{l1_backbone.name}' (position {position}).")
            except PAErr as e:
                return jsonify({'error': f'Level 1 plasmid assembly failed: {str(e)}'}), 400

        if guide_unit is None:
            return jsonify({'error': 'Could not create the Level 1 guide unit.'}), 500

        # ---- 3. Build the Level 2 cassette ----
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

        fillers = _load_fillers()
        selected = [guide_unit, cas_part, resistance_part] + others
        plan2 = plan_level2_components(selected, fillers)
        l2 = None
        if plan2['error']:
            result['messages'].append(f"Level 2 cassette not created — {plan2['error']}")
        else:
            components = plan2['ordered']
            result['l2_layout'] = plan2['layout']
            for w in plan2['warnings']:
                result['messages'].append(w)
            v = validate_assembly(components)
            if not v['valid']:
                result['messages'].append(
                    f"Level 2 cassette not created — components do not form a valid chain: {v['error']}")
            else:
                l2_name = _unique_part_name(names.get('l2_cassette') or f"{base_name}_L2", taken)
                try:
                    l2 = create_cassette(name=l2_name, owner_id=user.id, parts=components)
                    result['l2_cassette'] = {
                        'id': l2.id, 'name': l2.name, 'level': l2.level,
                        'length': len(l2.assembled_sequence), 'part_count': len(l2.part_ids),
                    }
                    result['messages'].append(f"Created Level 2 cassette '{l2.name}'.")
                except Exception as e:  # noqa: BLE001
                    result['messages'].append(f"Level 2 cassette not created — {str(e)}")

        # ---- 4. Optionally assemble the Level 2 plasmid ----
        if l2 is not None and data.get('create_plasmid'):
            l2_backbone_id = data.get('l2_backbone_id')
            if not l2_backbone_id:
                result['messages'].append('Level 2 plasmid not created — no Level 2 backbone selected.')
            else:
                backbone = Backbone.get_by_id(l2_backbone_id)
                if backbone is None:
                    result['messages'].append('Level 2 plasmid not created — backbone not found.')
                else:
                    pl_name = _unique_part_name(names.get('plasmid') or f"{base_name}_plasmid", taken)
                    try:
                        plasmid = assemble_plasmid(
                            backbone=backbone, cassettes=[l2], name=pl_name, owner_id=user.id)
                        result['plasmid'] = {
                            'id': plasmid.id, 'name': plasmid.name,
                            'length': len(plasmid.assembled_sequence),
                            'backbone_name': backbone.name,
                            'backbone_size': getattr(backbone, 'size', None),
                        }
                        result['messages'].append(f"Created Level 2 plasmid '{plasmid.name}'.")
                    except PAErr as e:
                        result['messages'].append(f"Level 2 plasmid not created — {str(e)}")

        # ---- 5. Classify messages into problems + actionable guidance ----
        _classify_problems(result, l1_acceptor=l1_acceptor,
                            create_plasmid=bool(data.get('create_plasmid')))

        return jsonify(result), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500
