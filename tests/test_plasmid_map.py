"""
Plasmid maps drawn as the Plasmid Editor draws them (app/services/plasmid_map.py).
"""

import re
import xml.etree.ElementTree as ET

from app.models.final_plasmid import FinalPlasmid
from app.models.user import User
from app.services.plasmid_map import find_sites, map_features, plasmid_map_svg

SVG = '{http://www.w3.org/2000/svg}'
# A 2 kb plasmid: EcoRI once, BamHI twice, the rest filler without either site.
SEQ = ('ACGT' * 100 + 'GAATTC' + 'ACGT' * 100 + 'GGATCC' + 'ACGT' * 100 + 'GGATCC').ljust(2000, 'T')
FEATURES = [
    {'type': 'promoter', 'label': 'p35S', 'start': 10, 'end': 300, 'strand': 1},
    {'type': 'CDS', 'label': 'GFP <bright> & "green"', 'start': 300, 'end': 1000, 'strand': 1},
    {'type': 'terminator', 'label': 'tNOS', 'start': 1000, 'end': 1250, 'strand': -1},
    {'type': 'misc_feature', 'label': 'off the end', 'start': 1900, 'end': 2500, 'strand': 1},
]


def _texts(svg):
    """Each label's words, without its hover title."""
    out = []
    for t in ET.fromstring(svg.split('\n', 1)[1]).iter(f'{SVG}text'):
        title = t.find(f'{SVG}title')
        out.append((t.text or '') + ((title.tail or '') if title is not None else ''))
    return out


def test_features_are_read_as_the_editor_reads_moclo_features():
    feats = map_features(FEATURES, len(SEQ))
    assert [f['name'] for f in feats] == ['p35S', 'GFP <bright> & "green"', 'tNOS'], 'one off the end is left out'
    assert feats[2]['strand'] == -1


def test_the_editors_default_enzymes_mark_the_unique_cutters():
    cuts = {}
    for s in find_sites(SEQ, circular=True):
        cuts.setdefault(s['enzyme'], []).append(s['cut_top'])
    assert cuts['EcoRI'] == [401], 'EcoRI cuts G^AATTC, after base 401'
    assert len(cuts['BamHI']) == 2
    texts = _texts(plasmid_map_svg('pTest', SEQ, FEATURES))
    assert 'EcoRI 402' in texts, 'labelled, 1-based, like the editor'
    assert not any(t.startswith('BamHI') for t in texts), 'only unique cutters are labelled'


def test_the_map_is_valid_svg_with_the_editors_colours_and_labels():
    svg = plasmid_map_svg('pTest', SEQ, FEATURES)
    root = ET.fromstring(svg.split('\n', 1)[1])
    assert root.tag == f'{SVG}svg'
    texts = _texts(svg)
    assert 'pTest' in texts and '2,000 bp' in texts
    assert 'GFP <bright> & "green"' in texts, 'names are escaped, not broken'
    strokes = {p.get('stroke') for p in root.iter(f'{SVG}path')}
    assert {'#34d399', '#60a5fa', '#f87171'} <= strokes, 'promoter, CDS and terminator as in the editor'


def test_a_crowded_map_grows_to_take_everything_in():
    many = [{'type': 'CDS', 'label': f'a rather long feature name {i}', 'start': 0, 'end': 1500, 'strand': 1}
            for i in range(30)]
    lo, _, side, _ = map(float, ET.fromstring(plasmid_map_svg('pBusy', SEQ, many).split('\n', 1)[1])
                         .get('viewBox').split())
    assert lo < 0 and side > 560
    small = ET.fromstring(plasmid_map_svg('pTest', SEQ, FEATURES[:1]).split('\n', 1)[1]).get('viewBox')
    assert small == '0 0 560 560', 'an ordinary map keeps the editor size'


def test_a_linear_map():
    svg = plasmid_map_svg('pLin', SEQ, FEATURES, circular=False)
    assert any(t and t.endswith('bp, linear') for t in _texts(svg))


def test_a_plasmids_map_is_served_and_downloads(client):
    User.create('alice', 'password123')
    assert client.post('/api/auth/login', json={'username': 'alice', 'password': 'password123'}).status_code == 200
    owner = User.get_by_username('alice')
    p = FinalPlasmid.create('pMap one', owner.id, 'bb', ['c1'], SEQ, FEATURES)
    r = client.get(f'/api/plasmids/{p.id}/map.svg')
    assert r.status_code == 200 and r.mimetype == 'image/svg+xml'
    assert b'p35S' in r.data and 'Content-Disposition' not in r.headers
    r = client.get(f'/api/plasmids/{p.id}/map.svg?download=1')
    assert re.search(r'attachment; filename="pMap_one_map.svg"', r.headers['Content-Disposition'])
    assert client.get('/api/plasmids/nothing/map.svg').status_code == 404
    client.post('/api/auth/logout')
    assert client.get(f'/api/plasmids/{p.id}/map.svg').status_code == 401
