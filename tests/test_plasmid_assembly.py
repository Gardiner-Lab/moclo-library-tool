"""
Tests for the cassette -> backbone (Level 1 -> Level 2) Golden Gate engine.

These check the biology of the join: the 4 bp fusion scars are kept exactly once
and the Type IIS recognition sites are removed from the product.
"""
import os
import tempfile

import pytest

from app.models.database import get_database
import app.models.database
from app.models.user import User
from app.models.part import Part
from app.models.backbone import Backbone
from app.services.assembly import create_cassette
from app.services.plasmid_assembly import (
    assemble_plasmid, simulate_assembly, AssemblyError, backbone_slots,
)
from app.services.restriction_sites import (
    build_moclo_acceptor, compute_slot_overhangs, reverse_complement,
)

SITES = ("GGTCTC", "GAGACC", "GAAGAC", "GTCTTC", "CGTCTC", "GAGACG")


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    app.models.database._db_instance = None
    db = get_database(path)
    db.initialize_schema()
    yield db
    if os.path.exists(path):
        os.unlink(path)
    app.models.database._db_instance = None


@pytest.fixture
def user(temp_db):
    return User.create(username="pa", password="password123")


def _l1_cassette(user, oh5, oh3, tag="c"):
    a = Part.create(name=f"{tag}-pro", part_type="NonCodingPromoter",
                    sequence=oh5 + "TATTAACCGG" * 4 + "AATG",
                    overhang_5prime=oh5, overhang_3prime="AATG",
                    lab_source="pa", contributor=user.username, level="0")
    b = Part.create(name=f"{tag}-term", part_type="NonCodingTerminator",
                    sequence="AATG" + "TTGGCCAATT" * 4 + oh3,
                    overhang_5prime="AATG", overhang_3prime=oh3,
                    lab_source="pa", contributor=user.username, level="0")
    return create_cassette(name=f"{tag}-L1", owner_id=user.id, parts=[a, b])


def _acceptor(user, oh5, oh3, enzyme="BpiI", name="acc"):
    seq = build_moclo_acceptor(oh5, oh3, enzyme=enzyme)
    return Backbone.create(name=name, owner_id=user.id, sequence=seq,
                           description="acceptor", restriction_sites=[],
                           overhang_5prime=oh5, overhang_3prime=oh3,
                           contributor=user.username, lab_source="pa")


def _count_sites(seq):
    seq = seq.upper()
    return {s: seq.count(s) for s in SITES}


def test_slot_detection_reads_overhangs_from_sequence(user):
    bb = _acceptor(user, "GGAG", "CGCT", enzyme="BpiI")
    slots = compute_slot_overhangs(bb.sequence)
    assert len(slots) == 1
    assert slots[0]["overhang_5prime"] == "GGAG"
    assert slots[0]["overhang_3prime"] == "CGCT"
    assert slots[0]["enzyme"] == "BpiI"
    # excision window contains both recognition motifs, not the overhangs
    window = bb.sequence[slots[0]["excise_start"]:slots[0]["excise_end"]]
    assert "GAAGAC" in window and "GTCTTC" in window
    assert bb.sequence[:slots[0]["excise_start"]].endswith("GGAG")
    assert bb.sequence[slots[0]["excise_end"]:].startswith("CGCT")


def test_single_cassette_join_is_faithful(user):
    cas = _l1_cassette(user, "GGAG", "CGCT")
    bb = _acceptor(user, "GGAG", "CGCT", enzyme="BpiI")
    slot = compute_slot_overhangs(bb.sequence)[0]

    pl = assemble_plasmid(bb, [cas], name="p", owner_id=user.id)
    prod = pl.assembled_sequence
    body = cas.assembled_sequence

    # exact Golden Gate product
    assert prod == bb.sequence[:slot["excise_start"]] + body[4:-4] + bb.sequence[slot["excise_end"]:]
    # the whole cassette, with both scars, appears exactly once
    assert prod.count(body) == 1
    # no Type IIS recognition site remains
    assert all(v == 0 for v in _count_sites(prod).values())
    # backbone arms preserved
    assert prod.startswith(bb.sequence[:slot["excise_start"] - 4])
    assert prod.endswith(bb.sequence[slot["excise_end"] + 4:])
    assert pl.metadata["moclo_level"] == 2


def test_reverse_orientation_join_is_faithful(user):
    # cassette whose forward overhangs only match the slot when reverse-complemented
    oh5, oh3 = "GGAG", "CGCT"
    cas = _l1_cassette(user, reverse_complement(oh3), reverse_complement(oh5))
    bb = _acceptor(user, oh5, oh3, enzyme="BpiI")
    slot = compute_slot_overhangs(bb.sequence)[0]

    pl = assemble_plasmid(bb, [cas], name="p", owner_id=user.id)
    prod = pl.assembled_sequence
    rc_body = reverse_complement(cas.assembled_sequence)

    assert pl.metadata["orientations"] == ["reverse"]
    assert prod == bb.sequence[:slot["excise_start"]] + rc_body[4:-4] + bb.sequence[slot["excise_end"]:]
    assert all(v == 0 for v in _count_sites(prod).values())


def test_seven_cassettes_chain_into_one_slot(user):
    J = ["GGAG", "AATG", "AGGT", "TTCG", "ACTA", "GCAA", "TCGC", "CGCT"]
    cassettes = [_l1_cassette(user, J[i], J[i + 1], tag=f"c{i+1}") for i in range(7)]
    bb = _acceptor(user, "GGAG", "CGCT", enzyme="BpiI")
    slot = compute_slot_overhangs(bb.sequence)[0]

    pl = assemble_plasmid(bb, cassettes, name="multi", owner_id=user.id)
    prod = pl.assembled_sequence

    # chained insert = c0 + c1[4:] + ... (each internal scar once)
    chained = cassettes[0].assembled_sequence
    for c in cassettes[1:]:
        chained += c.assembled_sequence[4:]
    assert prod == bb.sequence[:slot["excise_start"]] + chained[4:-4] + bb.sequence[slot["excise_end"]:]
    assert all(v == 0 for v in _count_sites(prod).values())
    for c in cassettes:
        assert c.assembled_sequence[4:-4] in prod


def test_non_chaining_cassettes_are_rejected(user):
    c1 = _l1_cassette(user, "GGAG", "AATG", tag="x1")
    c2 = _l1_cassette(user, "AGGT", "CGCT", tag="x2")   # 5' AGGT != c1 3' AATG
    bb = _acceptor(user, "GGAG", "CGCT", enzyme="BpiI")
    with pytest.raises(AssemblyError):
        assemble_plasmid(bb, [c1, c2], name="bad", owner_id=user.id)


def test_incompatible_cassette_is_rejected(user):
    cas = _l1_cassette(user, "GGAG", "TTAA")            # 3' TTAA != slot CGCT
    bb = _acceptor(user, "GGAG", "CGCT", enzyme="BpiI")
    with pytest.raises(AssemblyError):
        assemble_plasmid(bb, [cas], name="bad", owner_id=user.id)


def test_simulate_matches_assembly_length(user):
    cas = _l1_cassette(user, "GGAG", "CGCT")
    bb = _acceptor(user, "GGAG", "CGCT", enzyme="BpiI")
    sim = simulate_assembly(bb, [cas])
    pl = assemble_plasmid(bb, [cas], name="p", owner_id=user.id)
    assert sim["success"]
    assert sim["expected_length"] == len(pl.assembled_sequence)


def test_bsai_level1_acceptor_gives_level_1(user):
    cas = _l1_cassette(user, "GGAG", "CGCT")            # body has no BsaI sites
    bb = _acceptor(user, "GGAG", "CGCT", enzyme="BsaI")
    pl = assemble_plasmid(bb, [cas], name="p", owner_id=user.id)
    assert pl.metadata["moclo_level"] == 1
    assert all(v == 0 for v in _count_sites(pl.assembled_sequence).values())
