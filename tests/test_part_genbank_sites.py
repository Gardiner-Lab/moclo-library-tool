"""
A .gb whose cloning sites and declared overhangs disagree is refused by name.

A MoClo part carries exactly one pair of Type IIS sites, one at each end. Files
from outside often carry more — a whole plasmid, or a part that was wrapped in
sites twice — and then the pair the parser reads first is not the pair that
flanks the part. These tests check that the upload says what it found and what
that contradicts, rather than failing later on a bare "sequence must start with
its overhang", and that it does not guess which stretch is the part: that is for
the person to settle against their own sequence.
"""

import pytest

from app.services.part_genbank_parser_v2 import parse_part_genbank, PartGenBankError

BPII, BPII_REV = 'GAAGAC', 'GTCTTC'


def _dna(n, seed=1):
    """Bases with no BsaI or BpiI site, so only the sites a test adds count."""
    import random
    rng = random.Random(seed)
    while True:
        seq = ''.join(rng.choice('ACGT') for _ in range(n))
        if not any(s in seq for s in ('GGTCTC', 'GAGACC', BPII, BPII_REV)):
            return seq


def _genbank(sequence, overhang_5prime, overhang_3prime, name='pTest'):
    """A one-feature part record declaring its overhangs, as this tool exports."""
    head = [
        f"LOCUS       {name:<16} {len(sequence):>6} bp    DNA     linear   01-JAN-2026",
        "DEFINITION  Coding part - test",
        "FEATURES             Location/Qualifiers",
        f"     CDS             9..{len(sequence) - 8}",
        '                     /label="test part"',
        '                     /part_type="Coding"',
        f'                     /overhang_5prime="{overhang_5prime}"',
        f'                     /overhang_3prime="{overhang_3prime}"',
        '                     /moclo_level="1"',
        "ORIGIN",
    ]
    for i in range(0, len(sequence), 60):
        chunk = sequence[i:i + 60].lower()
        head.append(f"{i + 1:>9} " + ' '.join(chunk[j:j + 10] for j in range(0, len(chunk), 10)))
    head.append('//')
    return '\n'.join(head) + '\n'


def _wrap(body):
    """A part body flanked by one BpiI site at each end, as the exporter writes."""
    return f'{BPII}AA{body}TT{BPII_REV}'


def test_a_part_with_one_pair_of_sites_is_read():
    body = 'TAGT' + _dna(200) + 'TTGC'
    part = parse_part_genbank(_genbank(_wrap(body), 'TAGT', 'TTGC'), preferred_enzyme='BpiI')
    assert part['sequence'] == body
    assert (part['overhang_5prime'], part['overhang_3prime']) == ('TAGT', 'TTGC')
    assert part['level'] == '1'


def test_two_pairs_of_sites_are_refused_with_the_count_and_the_contradiction():
    """
    The shape of the file that prompted this: a Level 1 plasmid exported as a
    part, so the cassette's own flanks sit inside a second, outer pair.
    """
    cassette = 'TAGT' + _dna(300, seed=2) + 'TTGC'
    backbone = _dna(400, seed=3)
    plasmid = backbone + _wrap(cassette) + _dna(150, seed=4)
    with pytest.raises(PartGenBankError) as caught:
        parse_part_genbank(_genbank(_wrap(plasmid), 'TAGT', 'TTGC'), preferred_enzyme='BpiI')
    said = str(caught.value)

    assert '4 BpiI sites' in said and '2 × GAAGAC and 2 × GTCTTC' in said
    assert 'exactly two, one at each end' in said
    # What it declares, against what the first pair actually releases: the outer
    # forward site paired with the cassette's own reverse site, which is why the
    # fragment ends on TTGC but starts in the middle of the backbone.
    assert "5' TAGT and 3' TTGC" in said
    first_pair = len(backbone) + len(_wrap('')) - 8 + len(cassette)
    assert f'{first_pair} bp' in said
    # It sends them back to the sequence rather than naming a fragment itself:
    # a guess here would be read as the answer.
    assert 'Open the sequence and work out which stretch of it is the part' in said
    assert 'most likely' not in said
    assert f'{len(cassette)} bp' not in said
    assert 'positions' not in said
    # Not the old bare message from the validator.
    assert 'must start with' not in said


def test_one_pair_of_sites_with_overhangs_that_disagree_says_so():
    """Two sites, so nothing is ambiguous: the file simply contradicts itself."""
    body = 'TAGT' + _dna(120, seed=5) + 'TTGC'
    with pytest.raises(PartGenBankError) as caught:
        parse_part_genbank(_genbank(_wrap(body), 'CCAT', 'TTGC'), preferred_enzyme='BpiI')
    said = str(caught.value)
    assert "declares its overhangs as 5' CCAT and 3' TTGC" in said
    assert 'One of the two is wrong' in said
    # With one pair there is nothing to choose between, so it does not claim there is.
    assert 'which pair flanks the part' not in said
    assert 'Open the sequence and work out which stretch of it is the part' in said


def test_several_pairs_and_overhangs_matching_none_of_them_is_refused_the_same_way():
    """No fragment carries the declared overhangs, so there is nothing to point at either."""
    cassette = 'TAGT' + _dna(300, seed=6) + 'TTGC'
    plasmid = _dna(400, seed=7) + _wrap(cassette) + _dna(150, seed=8)
    with pytest.raises(PartGenBankError) as caught:
        parse_part_genbank(_genbank(_wrap(plasmid), 'AAAA', 'CCCC'), preferred_enzyme='BpiI')
    said = str(caught.value)
    assert '4 BpiI sites' in said
    assert "5' AAAA and 3' CCCC" in said
    assert 'Open the sequence and work out which stretch of it is the part' in said


def test_a_file_without_declared_overhangs_is_left_alone():
    """Nothing to disagree with: the overhangs come from the sites themselves."""
    body = 'TAGT' + _dna(200, seed=9) + 'TTGC'
    plasmid = _dna(300, seed=10) + _wrap(body) + _dna(100, seed=11)
    text = _genbank(_wrap(plasmid), 'TAGT', 'TTGC')
    text = '\n'.join(line for line in text.splitlines() if 'overhang_' not in line) + '\n'
    part = parse_part_genbank(text, preferred_enzyme='BpiI')
    assert part['sequence'].startswith(part['overhang_5prime'])
    assert part['sequence'].endswith(part['overhang_3prime'])
