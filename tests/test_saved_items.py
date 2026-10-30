"""Saved constructs and plasmids on the dashboard link to what they are of: the plasmid, or the cassette."""

from types import SimpleNamespace

import pytest

from app.models.cassette import Cassette
from app.models.final_plasmid import FinalPlasmid
from app.models.user import User


@pytest.fixture
def alice(monkeypatch):
    monkeypatch.setenv('SUITE_AUTH', 'proxy')
    User.create('alice', 'password123')
    plasmids = {'p-1': SimpleNamespace(name='pL2-tRFP')}
    cassettes = {'c-1': SimpleNamespace(name='35S:tRFP')}
    monkeypatch.setattr(FinalPlasmid, 'get_by_id', staticmethod(plasmids.get))
    monkeypatch.setattr(Cassette, 'get_by_id', staticmethod(cassettes.get))
    return {'X-Suite-User': 'alice'}


def test_a_saved_item_links_to_its_plasmid_or_cassette(client, alice):
    for title, kind, ref, summary in (('From a plasmid', 'plasmid', 'p-1', {}),
                                      ('A transcription unit', 'construct', 'c-1', {}),
                                      ('From the CRISPR Designer', 'construct', None, {'records': {'plasmid': {'id': 'p-1'}}}),
                                      ('Since deleted', 'plasmid', 'p-gone', {}),
                                      ('Of nothing', 'construct', None, {})):
        r = client.post('/api/me/saved', headers=alice, json={'item_type': kind, 'title': title, 'ref_id': ref, 'summary': summary})
        assert r.status_code == 201, r.get_json()
    links = {i['title']: i['link'] for i in client.get('/api/me/saved', headers=alice).get_json()['items']}
    assert links['From a plasmid'] == {'kind': 'plasmid', 'url': '/plasmids?view=p-1', 'name': 'pL2-tRFP'}
    assert links['A transcription unit'] == {'kind': 'cassette', 'url': '/cassettes?view=c-1', 'name': '35S:tRFP'}
    assert links['From the CRISPR Designer']['url'] == '/plasmids?view=p-1'
    assert links['Since deleted'] == {'kind': 'gone'}
    assert links['Of nothing'] is None
