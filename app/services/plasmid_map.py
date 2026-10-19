"""
Plasmid maps drawn the way the Plasmid Editor draws them.

A Python port of the editor's static/js/plasmidmap.js (circular and linear),
with its feature colours and its choice of enzymes, so a plasmid looks the
same here as when it is opened in the editor: feature arcs stacked outwards
with leader-line labels, a tick every ~10%, and the unique cutters of the
editor's default enzymes inside the circle. Keep the two in step.
"""

import math
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

# The editor's FEATURE_COLORS (static/js/api.js).
FEATURE_COLORS = {
    'CDS': '#60a5fa', 'promoter': '#34d399', 'terminator': '#f87171', 'rep_origin': '#fbbf24',
    'primer_bind': '#a78bfa', 'misc_feature': '#94a3b8', 'protein_bind': '#f472b6', 'RBS': '#2dd4bf',
    'regulatory': '#4ade80', 'intron': '#d1d5db', 'gene': '#93c5fd', 'enhancer': '#86efac',
    'polyA_signal': '#fca5a5', "5'UTR": '#a3e635', "3'UTR": '#fb923c',
}

# The editor's "Default" enzymes (dnakit/restriction.py).
DEFAULT_ENZYMES = [
    'AatII', 'AflII', 'AgeI', 'ApaI', 'AscI', 'AvrII', 'BamHI', 'BbsI', 'BglII', 'BsaI', 'BsmBI',
    'BspHI', 'BsrGI', 'BstBI', 'ClaI', 'DraI', 'EcoRI', 'EcoRV', 'FseI', 'HindIII', 'HpaI', 'KpnI',
    'MfeI', 'MluI', 'NcoI', 'NdeI', 'NheI', 'NotI', 'NruI', 'NsiI', 'PacI', 'PmeI', 'PstI', 'PvuI',
    'PvuII', 'SacI', 'SacII', 'SalI', 'SapI', 'ScaI', 'SbfI', 'SmaI', 'SpeI', 'SphI', 'StuI',
    'SwaI', 'XbaI', 'XhoI', 'XmaI', 'BspQI', 'PaqCI', 'BpiI', 'Esp3I',
]

FONT = 'system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif'
MAX_SITE_LABELS = 26


def _text_box(x: float, y: float, text: str, size: float, anchor: str):
    """Roughly where a label's text lies (an average glyph is ~0.6 of the font size wide)."""
    w = len(text) * size * 0.6
    left = x - w / 2 if anchor == 'middle' else (x - w if anchor == 'end' else x)
    return left, y - size, left + w, y + size


def _fit(boxes, size: float):
    """A square view, at least size wide, that takes in everything drawn (as the editor does)."""
    lo = min([0.0] + [b[0] - 8 for b in boxes] + [b[1] - 8 for b in boxes])
    hi = max([float(size)] + [b[2] + 8 for b in boxes] + [b[3] + 8 for b in boxes])
    lo = min(lo, size - hi)
    return lo, size - 2 * lo


def feature_color(f: Dict[str, Any]) -> str:
    return f.get('color') or FEATURE_COLORS.get(f.get('type')) or FEATURE_COLORS['misc_feature']


def map_features(raw: Optional[List[Dict[str, Any]]], n: int) -> List[Dict[str, Any]]:
    """
    MoClo features as the editor reads them when it opens a MoClo plasmid
    (moclo_bridge): 0-based start, exclusive end, inside the sequence.
    """
    out = []
    for i, f in enumerate(raw or []):
        if not isinstance(f, dict):
            continue
        try:
            start, end = int(f.get('start', 0)), int(f.get('end', 0))
        except (TypeError, ValueError):
            continue
        if end <= start or end > n:
            continue
        out.append({'id': i, 'name': str(f.get('label') or f.get('name') or 'feature'),
                    'type': f.get('type') or 'misc_feature', 'start': start, 'end': end,
                    'strand': -1 if f.get('strand') == -1 else 1})
    return out


def find_sites(sequence: str, circular: bool, enzymes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Cut positions of the editor's default enzymes: {'enzyme', 'cut_top'} (0-based)."""
    try:
        from Bio.Restriction import RestrictionBatch, AllEnzymes
        from Bio.Seq import Seq
    except ImportError:
        return []
    n = len(sequence)
    names = [e for e in (enzymes or DEFAULT_ENZYMES) if AllEnzymes.get(e, None) is not None]
    if not n or not names:
        return []
    found = RestrictionBatch(names).search(Seq(sequence.upper()), linear=not circular)
    sites = []
    for enzyme, cuts in found.items():
        for pos in cuts:
            cut = (pos - 1) % n if circular else pos - 1
            if circular or 0 < cut < n:
                sites.append({'enzyme': str(enzyme), 'cut_top': cut})
    sites.sort(key=lambda s: (s['cut_top'], s['enzyme']))
    return sites


def _label_sites(sites: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sites worth labelling: unique cutters first, then the rarest, capped."""
    counts: Dict[str, int] = {}
    for s in sites:
        counts[s['enzyme']] = counts.get(s['enzyme'], 0) + 1
    usable = list(sites)
    unique = [s for s in usable if counts[s['enzyme']] == 1]
    if unique:
        usable = unique
    usable.sort(key=lambda s: (counts[s['enzyme']], s['cut_top']))
    return sorted(usable[:MAX_SITE_LABELS], key=lambda s: s['cut_top'])


def _feat_length(f: Dict[str, Any], n: int) -> int:
    return f['end'] - f['start'] if f['end'] > f['start'] else n - f['start'] + f['end']


def _short(name: str, keep: int) -> str:
    return name if len(name) <= keep + 1 else name[:keep] + '…'


def _fmt(n: int) -> str:
    return f'{n:,}'


def _num(v: float) -> str:
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def _el(tag: str, attrs: Dict[str, Any], text: Optional[str] = None, title: Optional[str] = None) -> str:
    a = ''.join(f' {k}="{escape(_num(v) if isinstance(v, float) else str(v), {chr(34): "&quot;"})}"'
                for k, v in attrs.items() if v is not None)
    inner = (f'<title>{escape(title)}</title>' if title else '') + (escape(text) if text is not None else '')
    return f'<{tag}{a}>{inner}</{tag}>' if inner else f'<{tag}{a}/>'


def _feature_title(f: Dict[str, Any]) -> str:
    return f"{f['name']} ({f['type']}) {f['start'] + 1}..{f['end']}{' complement' if f['strand'] == -1 else ''}"


def plasmid_map_svg(name: str, sequence: str, features: Optional[List[Dict[str, Any]]],
                    circular: bool = True, sites: Optional[List[Dict[str, Any]]] = None) -> str:
    """The editor's map of this plasmid, as a standalone SVG file."""
    sequence = sequence or ''
    n = len(sequence)
    feats = map_features(features, n)
    if sites is None:
        sites = find_sites(sequence, circular)
    body = _circular(name, n, feats, sites) if circular else _linear(name, n, feats, sites)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def _circular(name: str, n: int, features: List[Dict[str, Any]], sites: List[Dict[str, Any]]) -> str:
    size = 560
    cx = cy = size / 2
    r = 170
    out: List[str] = []
    boxes: List[tuple] = []
    n = max(n, 1)

    def angle(pos: float) -> float:
        return (pos / n) * 2 * math.pi - math.pi / 2

    def point(pos: float, radius: float):
        return cx + radius * math.cos(angle(pos)), cy + radius * math.sin(angle(pos))

    def arc_path(frm: float, to: float, radius: float) -> str:
        x1, y1 = point(frm, radius)
        x2, y2 = point(to, radius)
        span = ((to - frm + n) % n) / n
        return f'M {_num(x1)} {_num(y1)} A {radius} {radius} 0 {1 if span > 0.5 else 0} 1 {_num(x2)} {_num(y2)}'

    out.append(_el('circle', {'cx': cx, 'cy': cy, 'r': r, 'fill': 'none', 'stroke': '#d1d5db', 'stroke-width': 8}))

    labelled_sites = _label_sites(sites)
    tick_clearance = (n / 360) * 9
    step = max(100, round(n / 10 / 100) * 100)
    for pos in range(0, n, step):
        x1, y1 = point(pos, r - 7)
        x2, y2 = point(pos, r + 7)
        out.append(_el('line', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'stroke': '#9ca3af', 'stroke-width': 1}))
        if any(min(abs(s['cut_top'] - pos), n - abs(s['cut_top'] - pos)) < tick_clearance for s in labelled_sites):
            continue
        lx, ly = point(pos, r - 15)
        out.append(_el('text', {'x': lx, 'y': ly, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
                                'font-size': 9, 'fill': '#6b7280'}, str(pos)))

    # Feature arcs, stacked outwards when they overlap.
    placed: List[Dict[str, Any]] = []
    for f in sorted(features, key=lambda f: -_feat_length(f, n)):
        fs, fe = f['start'], f['end']
        ring = 0
        while any(p['ring'] == ring and p['start'] < fe and fs < p['end'] for p in placed):
            ring += 1
        placed.append({'ring': ring, 'start': fs, 'end': fe})
        radius = r + 14 + ring * 13
        boxes.append((cx - radius - 8, cy - radius - 8, cx + radius + 8, cy + radius + 8))
        color = feature_color(f)
        out.append(_el('path', {'d': arc_path(fs, fe % n, radius), 'fill': 'none', 'stroke': color,
                                'stroke-width': 9, 'stroke-linecap': 'butt' if f['strand'] == -1 else 'round'},
                       title=_feature_title(f)))
        tip = fs if f['strand'] == -1 else fe % n
        tx, ty = point(tip, radius)
        a = angle(tip) + (math.pi if f['strand'] == -1 else 0)
        out.append(_el('polygon', {'points': '0,-6 11,0 0,6', 'fill': color,
                                   'transform': f'translate({_num(tx)} {_num(ty)}) rotate({_num(a * 180 / math.pi + 90)})'},
                       title=_feature_title(f)))

    # Labels with leader lines, alternating radius to limit collisions.
    labelled = [f for f in features if _feat_length(f, n) / n > 0.012 or len(features) < 24][:40]
    for i, f in enumerate(labelled):
        mid = (f['start'] + _feat_length(f, n) / 2) % n
        ring = next((p['ring'] for p in placed if p['start'] == f['start']), 0)
        outer = r + 20 + ring * 13
        x1, y1 = point(mid, outer + 6)
        x2, y2 = point(mid, outer + 24 + (i % 2) * 16)
        right = math.cos(angle(mid)) >= 0
        boxes.append(_text_box(x2 + (4 if right else -4), y2, _short(f['name'], 21), 10, 'start' if right else 'end'))
        out.append(_el('line', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'stroke': '#cbd5e1', 'stroke-width': 1}))
        out.append(_el('text', {'x': x2 + (4 if right else -4), 'y': y2, 'text-anchor': 'start' if right else 'end',
                                'dominant-baseline': 'middle', 'font-size': 10, 'fill': '#1f2937'},
                       _short(f['name'], 21), title=_feature_title(f)))

    # Restriction sites inside the circle, fanned out when neighbours are close.
    by_pos: Dict[int, List[Dict[str, Any]]] = {}
    for s in labelled_sites:
        by_pos.setdefault(s['cut_top'], []).append(s)
    min_gap = (n / 360) * 14
    last = -math.inf
    tier = 0
    for pos in sorted(by_pos):
        x1, y1 = point(pos, r - 4)
        x2, y2 = point(pos, r - 11)
        out.append(_el('line', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'stroke': '#b45309', 'stroke-width': 1.5}))
        tier = (tier + 1) % 3 if pos - last < min_gap else 0
        lx, ly = point(pos, r - (36 + tier * 16))
        right = math.cos(angle(pos)) >= 0
        here = by_pos[pos]
        out.append(_el('text', {'x': lx, 'y': ly, 'text-anchor': 'start' if right else 'end',
                                'dominant-baseline': 'middle', 'font-size': 9, 'fill': '#b45309'},
                       f"{','.join(s['enzyme'] for s in here[:2])} {pos + 1}",
                       title=f"{here[0]['enzyme']} cuts after base {pos}"))
        last = pos

    out.append(_el('text', {'x': cx, 'y': cy - 8, 'text-anchor': 'middle', 'font-size': 15, 'font-weight': 600,
                            'fill': '#1f2937'}, _short(name or 'Plasmid', 25)))
    out.append(_el('text', {'x': cx, 'y': cy + 12, 'text-anchor': 'middle', 'font-size': 12, 'fill': '#6b7280'},
                   f'{_fmt(n)} bp'))
    lo, side = _fit(boxes, size)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{_num(lo)} {_num(lo)} {_num(side)} {_num(side)}" '
            f'width="{_num(side)}" height="{_num(side)}" '
            f'role="img" aria-label="Circular map of {escape(name or "plasmid", {chr(34): "&quot;"})}" '
            f'font-family="{FONT}"><rect x="{_num(lo)}" y="{_num(lo)}" width="{_num(side)}" height="{_num(side)}" '
            f'fill="#ffffff"/>' + ''.join(out) + '</svg>')


def _linear(name: str, n: int, features: List[Dict[str, Any]], sites: List[Dict[str, Any]]) -> str:
    n = max(n, 1)
    width, pad_x = 760, 40
    usable = width - pad_x * 2

    def x(pos: float) -> float:
        return pad_x + (pos / n) * usable

    lanes: List[List[tuple]] = []
    placed: Dict[int, int] = {}
    for f in sorted(features, key=lambda f: f['start']):
        lane = 0
        while lane < len(lanes) and any(s < f['end'] and f['start'] < e for s, e in lanes[lane]):
            lane += 1
        if lane == len(lanes):
            lanes.append([])
        lanes[lane].append((f['start'], f['end']))
        placed[f['id']] = lane
    height = 110 + max(1, len(lanes)) * 26
    axis_y = 70
    out: List[str] = [_el('line', {'x1': pad_x, 'y1': axis_y, 'x2': width - pad_x, 'y2': axis_y,
                                   'stroke': '#9ca3af', 'stroke-width': 3})]
    step = max(100, round(n / 10 / 100) * 100)
    for pos in range(0, n + 1, step):
        out.append(_el('line', {'x1': x(pos), 'y1': axis_y + 4, 'x2': x(pos), 'y2': axis_y + 10,
                                'stroke': '#9ca3af', 'stroke-width': 1}))
        out.append(_el('text', {'x': x(pos), 'y': axis_y + 22, 'text-anchor': 'middle', 'font-size': 9,
                                'fill': '#6b7280'}, str(pos)))
    for f in features:
        y = axis_y + 36 + placed.get(f['id'], 0) * 26
        x1 = x(f['start'])
        x2 = max(x1 + 3, x(f['end'] if f['end'] > f['start'] else n))
        h = 14
        tip = min(9, max(0, (x2 - x1) / 2))
        if f['strand'] == -1:
            pts = [(x1 + tip, y), (x2, y), (x2, y + h), (x1 + tip, y + h), (x1, y + h / 2)]
        else:
            pts = [(x1, y), (x2 - tip, y), (x2, y + h / 2), (x2 - tip, y + h), (x1, y + h)]
        out.append(_el('polygon', {'points': ' '.join(f'{_num(a)},{_num(b)}' for a, b in pts),
                                   'fill': feature_color(f), 'stroke': '#ffffff', 'stroke-width': .5},
                       title=_feature_title(f)))
        if x2 - x1 > 34:
            out.append(_el('text', {'x': (x1 + x2) / 2, 'y': y + h / 2 + 1, 'text-anchor': 'middle',
                                    'dominant-baseline': 'middle', 'font-size': 9, 'fill': '#111827'},
                           _short(f['name'], 23), title=_feature_title(f)))
    by_pos: Dict[int, List[Dict[str, Any]]] = {}
    for s in _label_sites(sites):
        by_pos.setdefault(s['cut_top'], []).append(s)
    for flip, (pos, here) in enumerate(by_pos.items()):
        y = 20 + (flip % 2) * 16
        out.append(_el('line', {'x1': x(pos), 'y1': y + 8, 'x2': x(pos), 'y2': axis_y - 8,
                                'stroke': '#b45309', 'stroke-width': 1}))
        out.append(_el('text', {'x': x(pos), 'y': y, 'text-anchor': 'middle', 'font-size': 9, 'fill': '#b45309'},
                       f"{here[0]['enzyme']} {pos + 1}"))
    out.append(_el('text', {'x': pad_x, 'y': height - 8, 'font-size': 11, 'fill': '#6b7280'},
                   f'{name or "Sequence"} — {_fmt(n)} bp, linear'))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" role="img" aria-label="Linear map of {escape(name or "sequence", {chr(34): "&quot;"})}" '
            f'font-family="{FONT}"><rect width="{width}" height="{height}" fill="#ffffff"/>' + ''.join(out) + '</svg>')
