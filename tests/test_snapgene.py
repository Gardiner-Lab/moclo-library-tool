"""
SnapGene (.dna) files: exported beside GenBank, and accepted wherever GenBank is.

MoClo's exporters and parsers work in GenBank; app/services/file_formats.py
converts at the edges. These tests check the conversion both ways, that every
download has a SnapGene twin, and that uploads take a .dna file.
"""

import io
import random

from Bio import SeqIO

from app.models.backbone import Backbone
from app.models.part import Part
from app.models.user import User
from app.services import snapgene

GB = """LOCUS       pTest                    120 bp    DNA     circular SYN 01-JAN-2026
DEFINITION  test plasmid.
FEATURES             Location/Qualifiers
     CDS             10..69
                     /label="orf"
                     /ApEinfo_fwdcolor="#123456"
     promoter        complement(80..110)
                     /label="prom"
ORIGIN
"""


def genbank_text(seq):
    lines = [GB.replace('120 bp', f'{len(seq)} bp')]
    for i in range(0, len(seq), 60):
        chunk = seq[i:i + 60].lower()
        lines.append(f'{i + 1:>9} ' + ' '.join(chunk[j:j + 10] for j in range(0, len(chunk), 10)) + '\n')
    lines.append('//\n')
    return ''.join(lines)


def random_dna(n, seed=1):
    """Random bases with no BsaI or BpiI site, so only the sites a test adds count."""
    rng = random.Random(seed)
    while True:
        seq = ''.join(rng.choice('ACGT') for _ in range(n))
        if not any(site in seq for site in ('GGTCTC', 'GAGACC', 'GAAGAC', 'GTCTTC')):
            return seq


def test_genbank_and_snapgene_convert_both_ways():
    seq = random_dna(120)
    data = snapgene.from_genbank(genbank_text(seq))
    assert data[5:13] == b'SnapGene' and snapgene.is_snapgene(data)
    record = SeqIO.read(io.StringIO(snapgene.to_genbank(data, 'pTest')), 'genbank')
    assert str(record.seq).upper() == seq
    assert record.annotations['topology'] == 'circular'
    features = {f.qualifiers['label'][0]: f for f in record.features}
    assert (int(features['orf'].location.start), int(features['orf'].location.end)) == (9, 69)
    assert features['orf'].qualifiers['ApEinfo_fwdcolor'] == ['#123456']
    assert features['prom'].location.strand == -1


def signed_in(client):
    User.create('alice', 'password123', is_admin=True)
    assert client.post('/api/auth/login', json={'username': 'alice', 'password': 'password123'}).status_code == 200
    return client


def test_a_part_downloads_as_genbank_or_snapgene(client):
    signed_in(client)
    part = Part.create(name='pTest promoter', part_type='NonCodingPromoter', sequence=random_dna(90),
                       overhang_5prime='GGAG', overhang_3prime='TACT', lab_source='Lab', contributor='alice')
    gb = client.get(f'/api/parts/{part.id}/download/genbank')
    assert gb.status_code == 200 and gb.headers['Content-Disposition'].endswith('.gb')
    dna = client.get(f'/api/parts/{part.id}/download/snapgene')
    assert dna.status_code == 200, dna.get_data(as_text=True)
    assert dna.headers['Content-Disposition'].endswith('pTest_promoter.dna')
    assert dna.data[5:13] == b'SnapGene'
    # The same sequence as the GenBank file holds
    gb_record = SeqIO.read(io.StringIO(gb.get_data(as_text=True)), 'genbank')
    assert str(snapgene.read(dna.data).seq).upper() == str(gb_record.seq).upper()


def test_a_backbone_downloads_as_snapgene(client):
    signed_in(client)
    user = User.get_by_username('alice')
    backbone = Backbone.create(name='pBack', owner_id=user.id, sequence=random_dna(200, 2))
    r = client.get(f'/api/backbones/{backbone.id}/download/snapgene')
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.data[5:13] == b'SnapGene' and r.headers['Content-Disposition'].endswith('pBack.dna')


def test_a_backbone_uploads_from_a_snapgene_file(client):
    signed_in(client)
    # A backbone: two BsaI sites facing each other leave a GGAG..CGCT slot.
    seq = random_dna(100, 3) + 'GGTCTCAGGAG' + random_dna(120, 4) + 'CGCTTGAGACC' + random_dna(80, 5)
    data = snapgene.from_genbank(genbank_text(seq))
    r = client.post('/api/backbones', data={'file': (io.BytesIO(data), 'pUploaded.dna'), 'name': 'pUploaded'},
                    content_type='multipart/form-data')
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    saved = [b for b in Backbone.get_all() if b.name == 'pUploaded']
    assert saved and saved[0].sequence.upper() == seq


def test_other_files_are_still_refused(client):
    signed_in(client)
    r = client.post('/api/backbones', data={'file': (io.BytesIO(b'hello'), 'notes.txt'), 'name': 'x'},
                    content_type='multipart/form-data')
    assert r.status_code == 400
    assert 'SnapGene' in r.get_json()['message']
