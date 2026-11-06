"""
Who sees the MoClo library inside Trellis Tools: a record belongs to the labs
of whoever added it, and is seen by their chair group, by the chair groups that
group shares its library with, and by everyone when it is a reference record
(the built-in toolkit, or one an administrator marks). Administrators see all.
Outside the suite, everyone sees everything, as before.
"""

import sqlite3

import pytest

from app.models.backbone import Backbone
from app.models.part import Part
from app.models.user import User
from app.services import library_access

GATTACA = 'GATTACA' * 12


@pytest.fixture
def suite(tmp_path, monkeypatch):
    """
    Plant chair group: Gardiner Lab (ana, lead) and Smith Lab (zoe).
    Microbe chair group: Jones Lab (tom, its lead jim). Solo Lab (sol) is in none.
    """
    monkeypatch.setenv('SUITE_AUTH', 'proxy')
    path = tmp_path / 'suite.db'
    monkeypatch.setenv('SUITE_DATABASE_PATH', str(path))
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE chair_groups (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE labs (id TEXT PRIMARY KEY, name TEXT, chair_group_id TEXT);
        CREATE TABLE lab_members (username TEXT, lab_id TEXT, role TEXT, PRIMARY KEY (username, lab_id));
        INSERT INTO chair_groups VALUES ('plant', 'Plant Biology'), ('microbe', 'Microbiology');
        INSERT INTO labs VALUES ('g', 'Gardiner Lab', 'plant'), ('s', 'Smith Lab', 'plant'),
                                ('j', 'Jones Lab', 'microbe'), ('solo', 'Solo Lab', NULL);
        INSERT INTO lab_members VALUES ('ana', 'g', 'member'), ('lead', 'g', 'lab_lead'),
                                       ('zoe', 's', 'member'), ('tom', 'j', 'member'),
                                       ('jim', 'j', 'lab_lead'), ('sol', 'solo', 'member');
    """)
    conn.commit()
    conn.close()
    for name in ('ana', 'lead', 'zoe', 'tom', 'jim', 'sol'):
        User.create(name, 'password123')
    User.create('boss', 'password123', is_admin=True)
    User.create('system', 'password123')
    library_access._suite_cache = (None, {})
    yield path
    library_access._suite_cache = (None, {})


def who(name):
    return {'X-Suite-User': name}


def _part(name, contributor, lab_source='Gardiner Lab'):
    return Part.create(name=name, part_type='Coding', sequence=GATTACA, overhang_5prime='AATG',
                       overhang_3prime='GCTT', lab_source=lab_source, contributor=contributor)


def _listed(client, name):
    return {p['name'] for p in client.get('/api/parts', headers=who(name)).get_json()['parts']}


def test_a_part_is_its_chair_groups(suite, client):
    part = _part('anaCDS', 'ana')
    status = lambda name: client.get(f'/api/parts/{part.id}', headers=who(name)).status_code
    assert [status(n) for n in ('ana', 'lead', 'zoe', 'tom', 'sol', 'boss')] == [200, 200, 200, 403, 403, 200]
    assert 'anaCDS' in _listed(client, 'zoe') and 'anaCDS' not in _listed(client, 'tom')
    for route in ('compatible', 'translation', 'download/genbank'):
        assert client.get(f'/api/parts/{part.id}/{route}', headers=who('tom')).status_code == 403
    assert client.get(f'/api/visualize/part/{part.id}', headers=who('tom')).status_code == 403


def test_a_lab_in_no_chair_group_keeps_its_parts(suite, client):
    _part('solCDS', 'sol', 'Solo Lab')
    assert 'solCDS' in _listed(client, 'sol')
    assert not {'solCDS'} & (_listed(client, 'ana') | _listed(client, 'tom'))


def test_reference_parts_are_everyones(suite, client):
    _part('toolkit filler', 'system', 'MoClo toolkit')
    kit = _part('kit promoter', 'ana', library_access.PLANT_KIT_SOURCE)
    assert 'toolkit filler' in _listed(client, 'tom')
    assert 'kit promoter' not in _listed(client, 'tom')
    # An administrator marks it reference; only an administrator may.
    mark = lambda name, on: client.put('/api/library/reference', headers=who(name),
                                       json={'kind': 'part', 'id': kit.id, 'reference': on})
    assert mark('ana', True).status_code == 403
    assert mark('boss', True).status_code == 200
    assert 'kit promoter' in _listed(client, 'tom')
    assert next(p for p in client.get('/api/parts', headers=who('tom')).get_json()['parts']
                if p['name'] == 'kit promoter')['reference'] is True
    assert mark('boss', False).status_code == 200
    assert 'kit promoter' not in _listed(client, 'tom')


def test_the_bundled_plant_kit_is_marked_reference_once(suite, client):
    kit = _part('kit terminator', 'ana', library_access.PLANT_KIT_SOURCE)
    from app.models.database import get_database
    with get_database().get_connection() as conn:
        library_access.mark_plant_kit(conn.cursor())
    assert 'kit terminator' in _listed(client, 'tom')
    # Un-marked by an administrator, it stays un-marked through a restart.
    client.put('/api/library/reference', headers=who('boss'),
               json={'kind': 'part', 'id': kit.id, 'reference': False})
    with get_database().get_connection() as conn:
        library_access.mark_plant_kit(conn.cursor())
    assert 'kit terminator' not in _listed(client, 'tom')


def test_a_chair_group_shares_its_library_with_another(suite, client):
    _part('anaCDS', 'ana')
    share = lambda name, method='POST', frm='plant', to='microbe': client.open(
        '/api/library/sharing', method=method, headers=who(name), json={'from_group': frm, 'to_group': to})
    # Only an administrator or a lead of one of its labs shares a chair group's library.
    assert share('ana').status_code == 403
    assert share('jim').status_code == 403            # a lead, but of the other group
    r = share('lead')
    assert r.status_code == 200, r.get_json()
    assert [(s['from_name'], s['to_name']) for s in r.get_json()['shares']] == [('Plant Biology', 'Microbiology')]
    assert 'anaCDS' in _listed(client, 'tom')
    # One way: the Plant group does not see Microbiology's because of it.
    _part('tomCDS', 'tom', 'Jones Lab')
    assert 'tomCDS' not in _listed(client, 'ana')
    # Solo Lab, in no chair group, still sees neither.
    assert not {'anaCDS', 'tomCDS'} & _listed(client, 'sol')
    assert share('lead', 'DELETE').status_code == 200
    assert 'anaCDS' not in _listed(client, 'tom')


def test_sharing_needs_two_real_chair_groups(suite, client):
    bad = lambda frm, to: client.post('/api/library/sharing', headers=who('boss'),
                                      json={'from_group': frm, 'to_group': to}).status_code
    assert bad('plant', 'plant') == 400 and bad('plant', 'nowhere') == 400


def test_what_a_person_may_manage(suite, client):
    groups = {g['id']: g for g in client.get('/api/library/sharing', headers=who('lead')).get_json()['groups']}
    assert groups['plant']['mine'] and groups['plant']['manage'] and not groups['microbe']['manage']
    assert all(g['manage'] for g in client.get('/api/library/sharing', headers=who('boss')).get_json()['groups'])


def test_backbones_follow_the_same_rule(suite, client):
    ana = User.get_by_username('ana')
    backbone = Backbone.create(name='pAna', owner_id=ana.id, sequence=GATTACA * 3)
    names = lambda name: {b['name'] for b in client.get('/api/backbones', headers=who(name)).get_json()['backbones']}
    assert 'pAna' in names('zoe') and 'pAna' not in names('tom')
    assert client.get(f'/api/backbones/{backbone.id}', headers=who('tom')).status_code == 403
    system = User.get_by_username('system')
    Backbone.create(name='pToolkit', owner_id=system.id, sequence=GATTACA * 3)
    assert 'pToolkit' in names('tom')


def test_a_cassette_only_takes_parts_the_person_sees(suite, client):
    # A valid Level 1 chain: promoter (GGAG-AATG), CDS (AATG-GCTT), terminator (GCTT-CGCT).
    chain = [Part.create(name=n, part_type=t, sequence=GATTACA, overhang_5prime=o5, overhang_3prime=o3,
                         lab_source='Gardiner Lab', contributor='ana')
             for n, t, o5, o3 in (('pro', 'NonCodingPromoter', 'GGAG', 'AATG'),
                                  ('cds', 'Coding', 'AATG', 'GCTT'),
                                  ('ter', 'NonCodingTerminator', 'GCTT', 'CGCT'))]
    ids = [p.id for p in chain]
    assert client.post('/api/cassettes', headers=who('tom'),
                       json={'name': 'theirs', 'part_ids': ids}).status_code == 403
    made = client.post('/api/cassettes', headers=who('zoe'), json={'name': 'ours', 'part_ids': ids})
    assert made.status_code == 201, made.get_json()


def test_outside_the_suite_everyone_sees_everything(client, monkeypatch, tmp_path):
    monkeypatch.setenv('SUITE_DATABASE_PATH', str(tmp_path / 'absent.db'))
    library_access._suite_cache = (None, {})
    viewer = library_access.Viewer(User.create('loner', 'password123'))
    assert viewer.everything and viewer.sees('part', 'x', 'someone-else')


def test_the_plasmid_routes_answer_inside_the_suite(suite, client):
    # The routes catch their own errors and answer 500; a missing import hid there once.
    r = client.get('/api/plasmids', headers=who('ana'))
    assert r.status_code == 200, r.get_json()
    r = client.get('/api/backbones', headers=who('ana'))
    assert r.status_code == 200, r.get_json()
    assert client.get('/api/library/sharing', headers=who('ana')).status_code == 200
