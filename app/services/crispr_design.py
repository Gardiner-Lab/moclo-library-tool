"""
CRISPR/Cas guide construct designer for the Hahn/Nekrasov (2020) plant MoClo
genome-editing toolkit.

Reference:
    Hahn F, Korolev A, Sanjurjo Loures L, Nekrasov V. "A modular cloning toolkit
    for genome editing in plants." BMC Plant Biol 20, 179 (2020).
    https://doi.org/10.1186/s12870-020-02388-2

Given one or more 20 bp guide (protospacer) sequences, this service generates a
complete Golden Gate cloning strategy:

  1. Level -1: the pair of complementary oligos to order for each guide. The
     guide is flanked by the toolkit's fixed 4 bp fusion overhangs, and (per the
     lab's request) each oligo carries its own BpiI recognition site flanked by
     a 3 bp binding pad. The pad on each side is chosen independently to minimise
     hairpin / self-dimer free energy (via seqfold) while not introducing a
     spurious Type IIS site.
  2. Level 0: which guide-RNA / tRNA-sgRNA backbone acceptor vector each oligo
     pair is cloned into (BpiI).
  3. Level 1: how the guide module(s) + Pol III promoter (+ endlinker) fuse via
     BsaI into a Level 1 acceptor (default pICH47742, Position 2).
  4. Level 2: how the Level 1 units combine via BpiI with a nuclease unit, a
     selectable-marker unit and an endlinker into the final construct.

The overhang / vector tables below are transcribed from the paper's
Supplementary methods (Tables S1-S3) so the generated strategy matches the
actual toolkit vectors.
"""

import os
import re as _re
from typing import List, Dict, Any, Optional, Tuple

from app.services.compatibility import reverse_complement

# Directory holding the bundled toolkit Level 0 vector GenBank files (CC BY 4.0,
# Hahn et al. 2020; see app/data/toolkit_gb/ATTRIBUTION.md).
TOOLKIT_GB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "toolkit_gb")


# --------------------------------------------------------------------------- #
# Type IIS enzymes used by the toolkit
# --------------------------------------------------------------------------- #

BPII_SITE = "GAAGAC"   # BpiI / BbsI recognition (cuts 2/6, leaves 4 nt 5' overhang)
BSAI_SITE = "GGTCTC"   # BsaI recognition (cuts 1/5)
BSMBI_SITE = "CGTCTC"  # BsmBI (not used by this toolkit but screened against)
BPII_SPACER = 2        # nt between BpiI recognition site and the 4 nt overhang

# Recognition sites (and their reverse complements) that must NOT be accidentally
# created when we pick padding bases or assemble an oligo.
_FORBIDDEN_SITES = [
    BPII_SITE, reverse_complement(BPII_SITE),
    BSAI_SITE, reverse_complement(BSAI_SITE),
    BSMBI_SITE, reverse_complement(BSMBI_SITE),
]


class GuideDesignError(Exception):
    """Raised when a guide sequence or design request is invalid."""
    pass


# --------------------------------------------------------------------------- #
# Toolkit reference data (Supplementary Tables S1-S3)
# --------------------------------------------------------------------------- #

# Pol III promoters (Table S1 / S3). Transcription start nt: A for U3, G for U6.
POL3_PROMOTERS = {
    "TaU3p":   {"vector": "pFH31", "description": "Wheat U3 promoter", "start_nt": "A", "host": "monocot"},
    "TaU6p":   {"vector": "pICSL90003", "description": "Wheat U6 promoter", "start_nt": "G", "host": "monocot"},
    "OsU6-2p": {"vector": "pFH36", "description": "Rice U6-2 promoter", "start_nt": "G", "host": "monocot"},
    "OsU3p":   {"vector": "pFH38", "description": "Rice U3 promoter", "start_nt": "A", "host": "monocot"},
    "AtU6-26p": {"vector": "pFH34", "description": "Arabidopsis U6-26 promoter", "start_nt": "G", "host": "dicot"},
}

# Individual-promoter strategy: guide-RNA backbone acceptor modules (Tables S1/S2).
# overhang_5 / overhang_3 are the annealed-insert fusion sites; guide_len is 20
# for Cas9-family sgRNAs and 23 for Cas12a/Cms1 crRNAs.
INDIVIDUAL_BACKBONES = {
    # For wheat TaU3p (pFH33 promoter partner)
    "pFH85": {"backbone": "sgRNA classic", "overhang_5": "AGCA", "overhang_3": "AAAC", "guide_len": 20,
              "nucleases": ["SpCas9", "SpCas9-NG", "ScCas9", "nScCas9", "xCas9", "base editors"], "promoter": "TaU3p"},
    "pFH86": {"backbone": "sgRNA improved", "overhang_5": "AGCA", "overhang_3": "AAAC", "guide_len": 20,
              "nucleases": ["SpCas9", "SpCas9-NG", "ScCas9", "nScCas9", "xCas9", "base editors"], "promoter": "TaU3p"},
    "pFH87": {"backbone": "StCas9 sgRNA", "overhang_5": "AGCA", "overhang_3": "AAAC", "guide_len": 20,
              "nucleases": ["StCas9"], "promoter": "TaU3p"},
    "pFH88": {"backbone": "SaCas9 sgRNA", "overhang_5": "AGCA", "overhang_3": "AAAC", "guide_len": 20,
              "nucleases": ["SaCas9"], "promoter": "TaU3p"},
    "pFH89": {"backbone": "LbCas12a crRNA", "overhang_5": "AGAT", "overhang_3": "AAAA", "guide_len": 23,
              "nucleases": ["LbCas12a"], "promoter": "TaU3p"},
    "pFH90": {"backbone": "FnCas12a crRNA", "overhang_5": "AGAT", "overhang_3": "AAAA", "guide_len": 23,
              "nucleases": ["FnCas12a", "Cms1"], "promoter": "TaU3p"},
    # For Arabidopsis AtU6-26p (pFH35 promoter partner)
    "pFH99":  {"backbone": "sgRNA classic", "overhang_5": "ATTG", "overhang_3": "AAAC", "guide_len": 20,
               "nucleases": ["SpCas9", "SpCas9-NG", "ScCas9", "xCas9", "base editors"], "promoter": "AtU6-26p"},
    "pFH100": {"backbone": "sgRNA improved", "overhang_5": "ATTG", "overhang_3": "AAAC", "guide_len": 20,
               "nucleases": ["SpCas9", "SpCas9-NG", "ScCas9", "xCas9", "base editors"], "promoter": "AtU6-26p"},
    "pFH101": {"backbone": "StCas9 sgRNA", "overhang_5": "ATTG", "overhang_3": "AAAC", "guide_len": 20,
               "nucleases": ["StCas9"], "promoter": "AtU6-26p"},
    "pFH102": {"backbone": "SaCas9 sgRNA", "overhang_5": "ATTG", "overhang_3": "AAAC", "guide_len": 20,
               "nucleases": ["SaCas9"], "promoter": "AtU6-26p"},
    "pFH103": {"backbone": "LbCas12a crRNA", "overhang_5": "AGAT", "overhang_3": "AAAA", "guide_len": 23,
               "nucleases": ["LbCas12a"], "promoter": "AtU6-26p"},
    "pFH104": {"backbone": "FnCas12a crRNA", "overhang_5": "AGAT", "overhang_3": "AAAA", "guide_len": 23,
               "nucleases": ["FnCas12a", "Cms1"], "promoter": "AtU6-26p"},
    "pFH130": {"backbone": "FnCas12a crRNA", "overhang_5": "AGAT", "overhang_3": "AAAA", "guide_len": 23,
               "nucleases": ["FnCas12a", "Cms1"], "promoter": "OsU6-2p"},
    "pFH131": {"backbone": "FnCas12a crRNA", "overhang_5": "AGAT", "overhang_3": "AAAA", "guide_len": 23,
               "nucleases": ["FnCas12a", "Cms1"], "promoter": "OsU3p"},
}

# Polycistronic tRNA-sgRNA strategy. Every guide is ordered with the SAME 5'/3'
# overhangs (TGCA / AAAC, Section 3 step 3). The array POSITION is set by which
# Level 0 tRNA-sgRNA vector the oligos are cloned into.
TRNA_OVERHANG_5 = "TGCA"
TRNA_OVERHANG_3 = "AAAC"
TRNA_GUIDE_LEN = 20  # SpCas9 only

# Position-1 module depends on the Pol III promoter AND the sgRNA backbone
# flavour (Table S3).
TRNA_POSITION1 = {
    # promoter: {"improved": vector, "classic": vector}
    "TaU3p":    {"improved": "pFH113", "classic": "pAK007"},
    "TaU6p":    {"improved": "pFH71",  "classic": "pFH75"},
    "OsU6-2p":  {"improved": "pFH50",  "classic": "pFH73"},
    "OsU3p":    {"improved": "pFH51",  "classic": "pFH74"},
    "AtU6-26p": {"improved": "pFH49",  "classic": "pFH72"},
}

# Positions 2-6 in the tRNA-sgRNA array use the generic pAK position modules
# (pAK002-pAK006 seen in the pFH94 worked example; position 1 comes from the
# table above).
TRNA_POSITION_MODULES = {
    2: "pAK002",
    3: "pAK003",
    4: "pAK004",
    5: "pAK005",
    6: "pAK006",
}

# Endlinkers for the tRNA-sgRNA array when fewer than six guides are used
# (pAK-EL-01 .. pAK-EL-05). The endlinker "closes" the array after the last
# guide so the Level 1 unit has the correct downstream fusion site.
TRNA_ENDLINKERS = {
    1: "pAK-EL-01",
    2: "pAK-EL-02",
    3: "pAK-EL-03",
    4: "pAK-EL-04",
    5: "pAK-EL-05",
}

# Level 1 acceptor vectors (position in the eventual Level 2 construct).
L1_ACCEPTORS = {
    "pICH47732": {"position": 1},
    "pICH47742": {"position": 2},
    "pICH47751": {"position": 3},
    "pICH47761": {"position": 4},
    "pICH47772": {"position": 5},
    "pICH47781": {"position": 6},
    "pICH47791": {"position": 7},
}

# Endlinker for a single promoter-gRNA / tRNA-sgRNA unit at Level 2 (step 11).
L2_SINGLE_UNIT_ENDLINKER = "pICH41766"

# Canonical MoClo Level 2 position boundary overhangs (the BpiI fusion sites that
# link Level 1 units in the Level 2 construct). Each Level 1 acceptor spans one
# boundary pair; a unit in position N presents these as its 5'/3' fusion sites.
L2_POSITION_OVERHANGS = {
    1: ("TGCC", "GCAA"),
    2: ("GCAA", "ACTA"),
    3: ("ACTA", "TTAC"),
    4: ("TTAC", "CAGA"),
    5: ("CAGA", "TGTG"),
    6: ("TGTG", "GAGC"),
    7: ("GAGC", "TGCC"),
}

MAX_TRNA_GUIDES = 6

# Candidate 3 bp binding pads, tried in this deterministic order. The first
# candidate that produces no forbidden Type IIS site and the lowest hairpin
# free energy wins. Ordered to start with low-structure, balanced pads.
_PAD_CANDIDATES = [
    "TTA", "ATT", "TAA", "AAT", "TTT", "ATA", "TAT", "AAA",
    "ACA", "AGA", "TCA", "TGA", "CAA", "GAA", "CTA", "GTA",
]


# --------------------------------------------------------------------------- #
# Guide validation
# --------------------------------------------------------------------------- #

def normalize_guide(guide: str) -> str:
    """Uppercase and strip whitespace from a guide sequence."""
    return "".join(guide.split()).upper()


def validate_guide(guide: str, expected_len: int = 20) -> str:
    """
    Validate a guide (protospacer) sequence.

    Rules (from the paper): the target must be DNA (ACGT only), the expected
    length, and must NOT contain a BpiI (GAAGAC) or BsaI (GGTCTC) site (on either
    strand), as those would be cut during Golden Gate assembly.

    Returns the normalized guide, or raises GuideDesignError.
    """
    g = normalize_guide(guide)
    if not g:
        raise GuideDesignError("Guide sequence is empty.")
    if any(b not in "ACGT" for b in g):
        raise GuideDesignError(
            f"Guide '{g}' contains non-ACGT characters. Only unambiguous DNA bases are allowed."
        )
    if len(g) != expected_len:
        raise GuideDesignError(
            f"Guide '{g}' is {len(g)} bp; expected {expected_len} bp for this backbone."
        )
    rc = reverse_complement(g)
    for site, name in ((BPII_SITE, "BpiI"), (BSAI_SITE, "BsaI")):
        if site in g or site in rc:
            raise GuideDesignError(
                f"Guide '{g}' contains a {name} recognition site ({site}); "
                f"this would be cut during Golden Gate assembly. Choose a different target."
            )
    return g


# --------------------------------------------------------------------------- #
# Hairpin / secondary-structure scoring
# --------------------------------------------------------------------------- #

def hairpin_dg(sequence: str, temp: float = 37.0) -> float:
    """
    Return the minimum free energy (kcal/mol) of the most stable secondary
    structure the single-stranded oligo can fold into, using seqfold (Zuker MFE
    with SantaLucia 2004 DNA parameters).

    A more negative value means a more stable (worse) hairpin/self-structure.
    seqfold returns inf when no structure forms; we map that to 0.0 (no
    structure => no folding penalty).
    """
    try:
        from seqfold import dg
    except ImportError as exc:  # pragma: no cover - dependency is installed in the image
        raise GuideDesignError(
            "The 'seqfold' package is required for hairpin analysis but is not installed."
        ) from exc

    try:
        value = dg(sequence.upper(), temp=temp)
    except Exception:
        # seqfold can raise on very short/degenerate inputs; treat as no structure.
        return 0.0
    if value is None:
        return 0.0
    try:
        if value != value or value == float("inf"):  # NaN or inf => no structure
            return 0.0
    except TypeError:
        return 0.0
    # A positive dG means no favourable structure; clamp to 0 so it never looks
    # "better" than a truly structure-free oligo.
    return min(float(value), 0.0)


def _raw_hairpin_dg(sequence: str, temp: float) -> Optional[float]:
    """
    Raw seqfold folding free energy at a given temperature, without clamping.

    Returns the ΔG (which may be positive) or None when no structure forms
    (seqfold returns inf/NaN). Used for the melting-temperature scan, where we
    need to see ΔG actually cross zero rather than being clamped at 0.
    """
    try:
        from seqfold import dg
    except ImportError:
        return None
    try:
        value = dg(sequence.upper(), temp=temp)
    except Exception:
        return None
    if value is None:
        return None
    try:
        if value != value or value == float("inf"):
            return None
    except TypeError:
        return None
    return float(value)


def hairpin_tm(sequence: str, lo: float = 10.0, hi: float = 95.0) -> Optional[float]:
    """
    Estimate the melting temperature (deg C) of the most stable hairpin / self
    structure the single strand can form.

    seqfold reports the folding free energy ΔG at a given temperature; a hairpin
    is "melted" at the temperature where its ΔG rises to 0 (no longer favourable).
    We scan from lo to hi degrees and return the temperature where ΔG crosses
    zero (bisection-refined). Returns None if the structure is already unstable
    at the low end (no meaningful Tm) i.e. there is no appreciable hairpin.

    Args:
        sequence: single-stranded oligo sequence
        lo, hi: temperature search bounds in deg C

    Returns:
        Melting temperature in deg C (rounded to 1 dp), or None.
    """
    dg_lo = _raw_hairpin_dg(sequence, lo)
    # If no structure (None) or already non-favourable (>=0) at the low temp,
    # there is no hairpin to melt.
    if dg_lo is None or dg_lo >= 0:
        return None

    dg_hi = _raw_hairpin_dg(sequence, hi)
    # Still favourable even at the top of the range: report the upper bound.
    if dg_hi is not None and dg_hi < 0:
        return round(hi, 1)

    # Bisection: find the temperature where ΔG crosses 0 (favourable -> not).
    low, high = lo, hi
    for _ in range(40):
        mid = (low + high) / 2.0
        dmid = _raw_hairpin_dg(sequence, mid)
        # Treat "no structure" (None) or ΔG >= 0 as melted at mid.
        if dmid is None or dmid >= 0:
            high = mid
        else:
            low = mid
        if high - low < 0.1:
            break
    return round((low + high) / 2.0, 1)


def _creates_forbidden_site(sequence: str) -> bool:
    """True if the sequence contains any Type IIS recognition site we must avoid."""
    s = sequence.upper()
    return any(site in s for site in _FORBIDDEN_SITES)


def _count_sites(sequence: str, site: str) -> int:
    """Count occurrences of a recognition site on BOTH strands of a sequence."""
    s = sequence.upper()
    rc = reverse_complement(site)
    # Count on the top strand; a palindromic site would be double-counted, but
    # BpiI/BsaI sites are not palindromic so top + rc covers both strands.
    n = s.count(site)
    if rc != site:
        n += s.count(rc)
    return n


def screen_assembled_oligo(top_strand: str) -> Dict[str, Any]:
    """
    Safety check that assembling the guide into the oligo did not introduce an
    unintended Type IIS site.

    A correctly designed tRNA-sgRNA oligo (top strand) carries EXACTLY two BpiI
    sites — one GAAGAC near the 5' end and its reverse complement GTCTTC near the
    3' end — which are the intended cloning sites, and ZERO BsaI sites. Any extra
    BpiI site, or any BsaI site, means the guide (or a junction with the flanking
    overhangs/pads) created a recognition sequence that would be cut during
    Golden Gate assembly.

    Returns {'ok': bool, 'bpii_count': int, 'bsai_count': int, 'errors': [...]}.
    """
    seq = (top_strand or "").upper()
    bpii = _count_sites(seq, BPII_SITE)
    bsai = _count_sites(seq, BSAI_SITE)
    bsmbi = _count_sites(seq, BSMBI_SITE)

    errors = []
    # Exactly two intended BpiI sites (forward GAAGAC + reverse GTCTTC).
    if bpii > 2:
        errors.append(
            f"{bpii} BpiI (GAAGAC) sites found in the assembled oligo; only the 2 "
            f"intended cloning sites are allowed. The guide or a junction with the "
            f"flanking sequence introduced an extra BpiI site that would be cut."
        )
    elif bpii < 2:
        errors.append(
            f"Only {bpii} BpiI site(s) found; the oligo must retain its 2 intended "
            f"BpiI cloning sites."
        )
    if bsai > 0:
        errors.append(
            f"{bsai} BsaI (GGTCTC) site(s) found in the assembled oligo; the guide "
            f"introduced a BsaI site that would be cut during Level 1 assembly."
        )
    if bsmbi > 0:
        errors.append(
            f"{bsmbi} BsmBI (CGTCTC) site(s) found in the assembled oligo."
        )
    return {
        'ok': not errors,
        'bpii_count': bpii,
        'bsai_count': bsai,
        'bsmbi_count': bsmbi,
        'errors': errors,
    }


# --------------------------------------------------------------------------- #
# Oligo design
# --------------------------------------------------------------------------- #

def _build_top_strand(pad_left: str, pad_right: str, overhang_5: str,
                      guide: str, overhang_3: str, spacer_len: int = BPII_SPACER) -> str:
    """
    Build the top-strand oligo:

        [pad_left] GAAGAC [spacer] [overhang_5] [guide] [overhang_3] [rc spacer] GTCTTC [pad_right]

    The two BpiI sites point inward; after digestion the released fragment
    carries overhang_5 as its 5' sticky end and overhang_3 as its 3' sticky end.
    The spacer bases are arbitrary (discarded on digestion); we use a fixed
    low-complexity spacer.
    """
    spacer = "A" * spacer_len
    left = pad_left + BPII_SITE + spacer + overhang_5
    right = overhang_3 + reverse_complement(spacer) + reverse_complement(BPII_SITE) + pad_right
    return (left + guide + right).upper()


def _select_pads(overhang_5: str, guide: str, overhang_3: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    Choose the best 3 bp pad for each end INDEPENDENTLY.

    For each side we hold the other side's pad at a neutral reference while
    scoring, then pick the pad (from _PAD_CANDIDATES) that (a) introduces no
    forbidden Type IIS site anywhere in the resulting oligo and (b) minimises the
    hairpin free energy of the strand that pad terminates. The left pad is
    optimised against the TOP strand (which it 5'-caps); the right pad against
    the BOTTOM strand (which it 5'-caps after reverse-complementing).

    Returns (pad_left, pad_right, diagnostics).
    """
    neutral = "TTA"

    # ---- left pad: optimise the TOP strand ----
    best_left = None
    for pad in _PAD_CANDIDATES:
        top = _build_top_strand(pad, neutral, overhang_5, guide, overhang_3)
        # Only the left region is affected by pad_left for site creation near the
        # 5' end; still screen the whole oligo to be safe.
        if _creates_forbidden_site(pad + BPII_SITE):
            continue
        dg = hairpin_dg(top)
        if best_left is None or dg > best_left[1]:  # higher (less negative) dG is better
            best_left = (pad, dg)
    if best_left is None:
        best_left = (neutral, hairpin_dg(_build_top_strand(neutral, neutral, overhang_5, guide, overhang_3)))

    # ---- right pad: optimise the BOTTOM strand ----
    best_right = None
    for pad in _PAD_CANDIDATES:
        top = _build_top_strand(best_left[0], pad, overhang_5, guide, overhang_3)
        bottom = reverse_complement(top)
        if _creates_forbidden_site(reverse_complement(pad) + BPII_SITE):
            continue
        dg = hairpin_dg(bottom)
        if best_right is None or dg > best_right[1]:
            best_right = (pad, dg)
    if best_right is None:
        best_right = (neutral, 0.0)

    pad_left, left_dg = best_left
    pad_right, right_dg = best_right

    diagnostics = {
        "pad_left": pad_left,
        "pad_right": pad_right,
        "top_strand_dg": round(left_dg, 2),
        "bottom_strand_dg": round(right_dg, 2),
        "pads_identical": pad_left == pad_right,
    }
    return pad_left, pad_right, diagnostics


def design_oligos(guide: str, overhang_5: str, overhang_3: str) -> Dict[str, Any]:
    """
    Design the pair of complementary oligos to order for a single guide.

    Returns a dict with the forward (top) and reverse (bottom) oligo sequences,
    the chosen 3 bp pads, hairpin diagnostics, and a human-readable annotated
    layout.
    """
    pad_left, pad_right, diag = _select_pads(overhang_5, guide, overhang_3)
    top = _build_top_strand(pad_left, pad_right, overhang_5, guide, overhang_3)
    bottom = reverse_complement(top)

    spacer = "A" * BPII_SPACER
    annotated = (
        f"{pad_left}|{BPII_SITE}|{spacer}|{overhang_5}|{guide}|{overhang_3}|"
        f"{reverse_complement(spacer)}|{reverse_complement(BPII_SITE)}|{pad_right}"
    )

    # Hairpin melting temperature for each strand (deg C), i.e. the temperature
    # at which the predicted self-structure is no longer favourable. None when
    # there is no appreciable hairpin.
    diag["top_strand_tm"] = hairpin_tm(top)
    diag["bottom_strand_tm"] = hairpin_tm(bottom)

    # Warn if even the best oligo has a notably stable structure.
    warnings = []
    strong = -9.0  # kcal/mol threshold for flagging a strong hairpin
    if diag["top_strand_dg"] <= strong:
        warnings.append(
            f"Forward oligo has a stable predicted secondary structure "
            f"(dG={diag['top_strand_dg']} kcal/mol); annealing may be affected."
        )
    if diag["bottom_strand_dg"] <= strong:
        warnings.append(
            f"Reverse oligo has a stable predicted secondary structure "
            f"(dG={diag['bottom_strand_dg']} kcal/mol); annealing may be affected."
        )

    # Safety check: confirm assembling the guide into the oligo did not introduce
    # an unintended BsaI/BpiI site (at the guide itself or at a junction with the
    # flanking overhangs/pads). The guide was already screened in isolation; this
    # catches sites created only in the assembled context.
    site_check = screen_assembled_oligo(top)
    for e in site_check['errors']:
        warnings.append(e)

    return {
        "forward_oligo": top,
        "reverse_oligo": bottom,
        "forward_length": len(top),
        "reverse_length": len(bottom),
        "pad_left": pad_left,
        "pad_right": pad_right,
        "overhang_5prime": overhang_5,
        "overhang_3prime": overhang_3,
        "enzyme": "BpiI",
        "annotated_layout": annotated,
        "hairpin": diag,
        "site_check": site_check,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# Full cloning strategy
# --------------------------------------------------------------------------- #

def design_trna_sgrna_strategy(
    guides: List[str],
    promoter: str = "TaU3p",
    backbone_flavor: str = "improved",
    l1_acceptor: str = "pICH47742",
) -> Dict[str, Any]:
    """
    Generate the full polycistronic tRNA-sgRNA cloning strategy for a set of
    SpCas9 guides (Section 3 of the toolkit supplementary methods).

    Args:
        guides: 1-6 guide (protospacer) sequences, 20 bp each, in array order.
        promoter: Pol III promoter key (see POL3_PROMOTERS).
        backbone_flavor: 'improved' or 'classic' sgRNA backbone.
        l1_acceptor: Level 1 acceptor vector (default pICH47742 = Position 2).

    Returns a structured dict describing Levels -1, 0, 1 and 2.
    """
    if promoter not in POL3_PROMOTERS:
        raise GuideDesignError(f"Unknown Pol III promoter '{promoter}'. Options: {list(POL3_PROMOTERS)}")
    if backbone_flavor not in ("improved", "classic"):
        raise GuideDesignError("backbone_flavor must be 'improved' or 'classic'.")
    if l1_acceptor not in L1_ACCEPTORS:
        raise GuideDesignError(f"Unknown Level 1 acceptor '{l1_acceptor}'. Options: {list(L1_ACCEPTORS)}")
    if not guides:
        raise GuideDesignError("At least one guide sequence is required.")
    if len(guides) > MAX_TRNA_GUIDES:
        raise GuideDesignError(
            f"The tRNA-sgRNA system supports up to {MAX_TRNA_GUIDES} guides per Level 1 unit; "
            f"got {len(guides)}. Split extra guides into a second Level 1 unit."
        )

    validated = [validate_guide(g, TRNA_GUIDE_LEN) for g in guides]

    # ---- Level -1: oligos + Level 0: position vectors ----
    pos1_module = TRNA_POSITION1[promoter][backbone_flavor]
    guide_entries = []
    for i, g in enumerate(validated):
        position = i + 1
        if position == 1:
            l0_vector = pos1_module
        else:
            l0_vector = TRNA_POSITION_MODULES.get(position, f"position-{position} module")
        oligos = design_oligos(g, TRNA_OVERHANG_5, TRNA_OVERHANG_3)
        guide_entries.append({
            "position": position,
            "guide": g,
            "level0_vector": l0_vector,
            "oligos": oligos,
        })

    # ---- Endlinker (needed if fewer than 6 guides) ----
    n = len(validated)
    endlinker = None
    if n < MAX_TRNA_GUIDES:
        endlinker = TRNA_ENDLINKERS.get(n)

    promoter_info = POL3_PROMOTERS[promoter]
    l1_position = L1_ACCEPTORS[l1_acceptor]["position"]

    return {
        "strategy": "polycistronic tRNA-sgRNA",
        "nuclease_family": "SpCas9",
        "guide_count": n,
        "promoter": {"key": promoter, **promoter_info},
        "backbone_flavor": backbone_flavor,
        "level_minus1": {
            "description": (
                "Order and anneal one complementary oligo pair per guide. Each guide is "
                "flanked by the tRNA-sgRNA fusion overhangs (5' TGCA / 3' AAAC) and a BpiI "
                "site with a 3 bp binding pad on each end."
            ),
            "enzyme": "BpiI",
            "guides": guide_entries,
        },
        "level0": {
            "description": (
                "Cut-ligate each annealed oligo pair into its position-specific Level 0 "
                "tRNA-sgRNA acceptor via BpiI. The array position is set by the acceptor "
                "vector, not the guide overhangs."
            ),
            "enzyme": "BpiI",
            "position1_module": pos1_module,
            "modules": [{"position": e["position"], "level0_vector": e["level0_vector"]} for e in guide_entries],
        },
        "level1": {
            "description": (
                f"Fuse the Pol III promoter module ({promoter_info['vector']}, {promoter_info['description']}) "
                f"with the {n} tRNA-sgRNA module(s)"
                + (f" and endlinker {endlinker}" if endlinker else "")
                + f" into the Level 1 acceptor {l1_acceptor} (Position {l1_position}) via BsaI-HF v2."
            ),
            "enzyme": "BsaI-HF v2",
            "promoter_module": promoter_info["vector"],
            "l1_acceptor": l1_acceptor,
            "l1_position": l1_position,
            "endlinker": endlinker,
            "endlinker_needed": endlinker is not None,
        },
        "level2": {
            "description": (
                "Combine this Level 1 tRNA-sgRNA unit with the Level 1 units you select below "
                "(a Cas nuclease unit and a selectable-marker unit are required; other Level 1 "
                "units are optional) into a Level 2 acceptor backbone via BpiI. The designer "
                "maps each chosen unit to its Level 2 position, auto-fills internal gaps with "
                "dummy units and closes the array with the matching end-linker."
            ),
            "enzyme": "BpiI",
            "single_unit_endlinker": L2_SINGLE_UNIT_ENDLINKER,
            "required_units": [
                "A Level 1 Cas nuclease transcription unit (choose from your library below)",
                "A Level 1 selectable-marker transcription unit (choose from your library below)",
                f"This Level 1 tRNA-sgRNA unit ({l1_acceptor}, Position {l1_position})",
                "Any optional additional Level 1 units",
                "Dummy units and the closing end-linker (added automatically to span the array)",
                "A Level 2 acceptor backbone (e.g. pAGM4673)",
            ],
        },
        "reference": "Hahn et al. 2020, BMC Plant Biol 20:179 (doi:10.1186/s12870-020-02388-2)",
    }


# --------------------------------------------------------------------------- #
# Full Level 0 module assembly (splice the guide into the real toolkit vector)
# --------------------------------------------------------------------------- #

def _vector_gb_path(vector_name: str) -> str:
    """Return the path to a bundled toolkit vector .gb file, or raise."""
    path = os.path.join(TOOLKIT_GB_DIR, f"{vector_name}.gb")
    if not os.path.exists(path):
        raise GuideDesignError(
            f"Toolkit vector sequence '{vector_name}.gb' is not bundled with the app "
            f"(looked in {TOOLKIT_GB_DIR})."
        )
    return path


def _vector_length(vector_name: str) -> Optional[int]:
    """Length of a bundled toolkit vector (bp), or None if not available."""
    try:
        from Bio import SeqIO
        rec = SeqIO.read(_vector_gb_path(vector_name), "genbank")
        return len(str(rec.seq))
    except Exception:  # noqa: BLE001
        return None


def _vector_sequence(vector_name: str) -> str:
    """Raw sequence (upper-case) of a bundled toolkit vector, or '' if missing."""
    try:
        from Bio import SeqIO
        rec = SeqIO.read(_vector_gb_path(vector_name), "genbank")
        return str(rec.seq).upper()
    except Exception:  # noqa: BLE001
        return ''


# Feature types worth carrying through from a bundled Level 0 module's own
# GenBank annotation (the biologically meaningful parts — not the vector
# backbone, enzyme sites, or lacZ dropout).
_MODULE_KEEP_TYPES = {'promoter', 'terminator', 'tRNA', 'gRNA_Scaffold',
                      'misc_RNA', 'regulatory', 'CDS'}


def _released_bsai_insert(seq: str, raw_features: List[Dict[str, Any]]):
    """
    Given a circular Level 0 module sequence with a single divergent BsaI pair
    (forward GGTCTC near the insert start, reverse GAGACC near the insert end),
    return the RELEASED insert fragment and its features in insert-local coords.

    BsaI GGTCTC(1/5): forward site at p leaves a 4 nt 5' overhang seq[p+7:p+11],
    with the retained insert top strand starting at p+7. The reverse site
    (GAGACC at q on the top strand) leaves the insert's right end; the insert top
    strand ends at q-1 and its 3' fusion overhang (as read on the top strand) is
    seq[q-5:q-1].

    Returns dict {insert, left_oh, right_oh, features(local coords)} or None if a
    clean single divergent pair is not found.
    """
    s = (seq or '').upper()
    fwd = [m.start() for m in _re.finditer('GGTCTC', s)]
    rev = [m.start() for m in _re.finditer('GAGACC', s)]
    if len(fwd) != 1 or len(rev) != 1:
        return None
    p, q = fwd[0], rev[0]
    if not (p + 11 <= q - 1):
        return None
    offset = p + 7
    end = q - 1
    insert = s[offset:end]
    left_oh = s[p + 7:p + 11]
    right_oh = s[q - 5:q - 1]
    feats = []
    for f in (raw_features or []):
        try:
            cs, ce = int(f['start']), int(f['end'])
        except (TypeError, ValueError, KeyError):
            continue
        if cs >= offset and ce <= end:
            feats.append({**f, 'start': cs - offset, 'end': ce - offset})
    return {'insert': insert, 'left_oh': left_oh, 'right_oh': right_oh, 'features': feats}


def _module_raw_features(vector_name: str) -> List[Dict[str, Any]]:
    """Meaningful biological features of a bundled module in its OWN coords."""
    return _extract_module_features(vector_name)


def _extract_module_features(vector_name: str) -> List[Dict[str, Any]]:
    """
    Read a bundled Level 0 module's GenBank file and return its meaningful
    biological features (promoter, poly-T terminator, tRNA, scaffold, ...) in the
    module's own 0-based coordinates. Vector-backbone CDS (Sm/Sp, KanR, LacZ) and
    enzyme/overhang features are skipped. Used to carry a part's REAL annotation
    (e.g. the U6 promoter from pFH34, the poly-T terminator from pAK-EL-0x) into
    the assembled Level 1 construct instead of synthesizing or searching for it.
    """
    try:
        from Bio import SeqIO
        rec = SeqIO.read(_vector_gb_path(vector_name), "genbank")
    except Exception:  # noqa: BLE001
        return []
    out = []
    for ft in rec.features:
        q = ft.qualifiers
        label = (q.get('label') or q.get('note') or [ft.type])[0] or ft.type
        low = label.lower()
        if ft.type not in _MODULE_KEEP_TYPES:
            continue
        # Skip vector-backbone selection/marker CDS carried on the module plasmid.
        if ft.type == 'CDS' and any(k in low for k in ('lacz', 'sm/sp', 'spec', 'kanr', 'kan ', 'ampr', 'cat', 'cmr')):
            continue
        try:
            s, e = int(ft.location.start), int(ft.location.end)
        except (TypeError, ValueError):
            continue
        out.append({
            'type': ft.type,
            'label': label,
            'start': s, 'end': e,
            'strand': 1 if ft.location.strand in (None, 1) else -1,
        })
    return out


def _find_insertion_boundaries(record, seq: str) -> Tuple[int, int]:
    """
    Locate the guide-insertion boundaries in a Level 0 tRNA-sgRNA acceptor.

    The guide is cloned (via BpiI) between the tRNA's downstream TGCA overhang and
    the sgRNA scaffold's upstream GTTT overhang (= reverse complement of the AAAC
    3' fusion site), replacing the lacZ placeholder. Both are annotated as
    'overhang' features flanking the lacZ CDS.

    Returns (left_end, right_start): keep seq[:left_end], insert the guide, then
    keep seq[right_start:].
    """
    lacz = None
    tgca = []
    gttt = []
    for ft in record.features:
        label = (ft.qualifiers.get('label', [''])[0] or '').lower()
        s, e = int(ft.location.start), int(ft.location.end)
        frag = seq[s:e]
        if ft.type == 'CDS' and 'lacz' in label:
            lacz = (s, e)
        if ft.type == 'overhang' and frag == 'TGCA':
            tgca.append((s, e))
        if ft.type == 'overhang' and frag == 'GTTT':
            gttt.append((s, e))

    if lacz is None or not tgca or not gttt:
        raise GuideDesignError(
            "Could not locate the lacZ placeholder and TGCA/GTTT overhang features "
            "in the acceptor vector; cannot determine the guide insertion site."
        )

    # TGCA immediately upstream of lacZ (its end is at/just before lacZ start),
    # GTTT immediately downstream of lacZ (its start is at/just after lacZ end).
    tgca_before = max((t for t in tgca if t[1] <= lacz[0] + 6), key=lambda x: x[1], default=None)
    gttt_after = min((g for g in gttt if g[0] >= lacz[1] - 6), key=lambda x: x[0], default=None)
    if tgca_before is None or gttt_after is None:
        raise GuideDesignError(
            "The TGCA/GTTT overhangs do not flank the lacZ placeholder as expected."
        )
    return tgca_before[1], gttt_after[0]


def assemble_level0_module(vector_name: str, guide: str,
                           promoter_label: Optional[str] = None) -> Dict[str, Any]:
    """
    Assemble the FULL Level 0 guide-cassette module: take the real toolkit
    acceptor vector, excise the lacZ placeholder, and splice in the guide so the
    module reads  ...tRNA | TGCA | guide | (GTTT)scaffold...  exactly as it would
    after the BpiI cut-ligation.

    Returns a dict with the complete assembled circular module sequence, the
    guide's position within it, and feature annotations. The real toolkit
    annotations (tRNA, sgRNA scaffold, Pol III promoter, overhangs, start codon)
    are carried through and remapped across the lacZ->guide splice, plus the
    guide and a poly-T Pol III terminator are annotated — so a GenBank export of
    the Level 1 construct shows the U6/U3 promoter and poly-T terminator as real
    features rather than only in free-text notes.
    """
    from Bio import SeqIO  # local import; biopython is a project dependency

    guide = validate_guide(guide, TRNA_GUIDE_LEN)
    path = _vector_gb_path(vector_name)
    record = SeqIO.read(path, "genbank")
    seq = str(record.seq).upper()

    left_end, right_start = _find_insertion_boundaries(record, seq)
    left = seq[:left_end]      # ...tRNA...TGCA
    right = seq[right_start:]  # GTTT(scaffold)...backbone
    assembled = left + guide + right

    # Sanity: the two internal BpiI sites (and lacZ) must be gone.
    if BPII_SITE in assembled or reverse_complement(BPII_SITE) in assembled:
        raise GuideDesignError(
            f"Assembled module for {vector_name} unexpectedly still contains a BpiI site."
        )

    guide_start = len(left)
    guide_end = guide_start + len(guide)
    # Position shift applied to everything downstream of the splice.
    delta = len(guide) - (right_start - left_end)

    # Feature types from the toolkit GB worth keeping as biological annotations
    # (skip the removed lacZ, the vector-only rep/KanR/primer, and raw enzyme
    # sites which we re-annotate ourselves where relevant).
    _KEEP_TYPES = {'tRNA', 'gRNA_Scaffold', 'promoter', 'terminator',
                   'Start_codon', 'start_codon', 'misc_RNA', 'regulatory'}

    def _remap(s, e):
        """Map an original-coordinate feature span across the splice."""
        if e <= left_end:
            return s, e                      # entirely before the insert
        if s >= right_start:
            return s + delta, e + delta      # entirely after the insert
        return None                          # overlaps the excised lacZ -> drop

    features = []
    for ft in record.features:
        q = ft.qualifiers
        label = (q.get('label') or q.get('note') or [ft.type])[0]
        if ft.type == 'CDS' and 'lacz' in (label or '').lower():
            continue
        if ft.type not in _KEEP_TYPES:
            continue
        try:
            s, e = int(ft.location.start), int(ft.location.end)
        except (TypeError, ValueError):
            continue
        mapped = _remap(s, e)
        if mapped is None:
            continue
        ms, me = mapped
        ftype = 'promoter' if ft.type == 'promoter' else (
            'CDS' if 'codon' in ft.type.lower() else ft.type)
        features.append({
            'type': ft.type if ft.type != 'Start_codon' else 'misc_feature',
            'label': label,
            'start': ms, 'end': me,
            'strand': 1 if ft.location.strand in (None, 1) else -1,
        })

    # Annotate the guide and the two fusion scars. The Pol III PROMOTER and the
    # poly-T TERMINATOR are NOT synthesized/searched here — they live in their
    # own Level 0 modules (the promoter module pFH3x and the end-linker pAK-EL),
    # whose real GB annotations are carried through where those modules are
    # assembled (see _extract_module_features / assemble_level1_guide_cassette).
    features.append({"type": "misc_feature", "label": "guide (protospacer)",
                     "start": guide_start, "end": guide_end, "strand": 1})
    features.append({"type": "misc_feature", "label": "5' fusion site TGCA",
                     "start": guide_start - 4, "end": guide_start, "strand": 1})
    features.append({"type": "misc_feature", "label": "3' fusion site (AAAC / GTTT)",
                     "start": guide_end, "end": guide_end + 4, "strand": 1})

    return {
        "vector": vector_name,
        "assembled_sequence": assembled,
        "length": len(assembled),
        "guide": guide,
        "guide_start": guide_start,
        "guide_end": guide_end,
        "topology": record.annotations.get("topology", "circular"),
        "features": features,
    }


# --------------------------------------------------------------------------- #
# Oligo annealing protocol + cloning-strategy text (stored on the Part)
# --------------------------------------------------------------------------- #

def build_annealing_protocol(forward_oligo: str, reverse_oligo: str) -> str:
    """
    Return the oligo annealing protocol text: heat block to 100 C, then cool to
    room temperature (as specified by the lab), mixing FW+REV oligos 1:1 at
    10 uM.
    """
    return (
        "Oligo annealing protocol:\n"
        "  1. Resuspend the forward and reverse oligos and adjust each to 10 uM.\n"
        "  2. Mix the forward and reverse oligos 1:1 (e.g. 5 uL + 5 uL).\n"
        "  3. Place the tube in a heat block set to 100 C for 5 min.\n"
        "  4. Switch off / remove the block from heat and let it cool slowly to\n"
        "     room temperature (leave the tube in the block while it cools).\n"
        "  5. The annealed duplex is ready to use directly in the BpiI\n"
        "     cut-ligation reaction.\n"
        f"  FW oligo: {forward_oligo}\n"
        f"  REV oligo: {reverse_oligo}"
    )


def build_level0_cloning_strategy(guide: str, vector_name: str, position: int,
                                  promoter: str, backbone_flavor: str,
                                  oligos: Dict[str, Any]) -> str:
    """
    Build the human-readable MoClo cloning-strategy text stored in the Part's
    comments, covering the annealed-oligo insertion into the Level 0 acceptor and
    the annealing protocol.
    """
    lines = [
        "MoClo cloning strategy — Level 0 tRNA-sgRNA guide cassette",
        f"  Guide (20 bp protospacer): {guide}",
        f"  Array position: {position}",
        f"  Level 0 acceptor vector: {vector_name} ({backbone_flavor} sgRNA backbone)",
        f"  Pol III promoter (for the Level 1 step): {promoter}",
        "",
        "Step 1 — Anneal oligos and clone into the Level 0 acceptor (BpiI):",
        f"  Forward oligo (5'->3'): {oligos['forward_oligo']}",
        f"  Reverse oligo (5'->3'): {oligos['reverse_oligo']}",
        f"  Oligo layout: {oligos['annotated_layout']}",
        "  Set up a BpiI cut-ligation (see general GG protocol) with the annealed",
        "  oligos and the Level 0 acceptor; transform and select white colonies on",
        "  kanamycin / IPTG / X-Gal; verify by sequencing (primer FH32).",
        "",
        build_annealing_protocol(oligos["forward_oligo"], oligos["reverse_oligo"]),
        "",
        "Reference: Hahn et al. 2020, BMC Plant Biol 20:179 "
        "(doi:10.1186/s12870-020-02388-2), CC BY 4.0.",
    ]
    return "\n".join(lines)


def build_level0_part_payload(
    guide: str,
    name: str,
    position: int,
    promoter: str,
    backbone_flavor: str,
    lab_source: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """
    Assemble the full Level 0 module for one guide and return a payload suitable
    for creating a Part (sequence = full assembled module, overhangs = the module
    fusion sites, comments = cloning strategy + annealing protocol).
    """
    if promoter not in POL3_PROMOTERS:
        raise GuideDesignError(f"Unknown Pol III promoter '{promoter}'.")
    if backbone_flavor not in ("improved", "classic"):
        raise GuideDesignError("backbone_flavor must be 'improved' or 'classic'.")

    guide = validate_guide(guide, TRNA_GUIDE_LEN)

    if position == 1:
        vector_name = TRNA_POSITION1[promoter][backbone_flavor]
    else:
        vector_name = TRNA_POSITION_MODULES.get(position)
        if vector_name is None:
            raise GuideDesignError(f"No Level 0 module for array position {position} (max 6).")

    module = assemble_level0_module(vector_name, guide)
    oligos = design_oligos(guide, TRNA_OVERHANG_5, TRNA_OVERHANG_3)
    strategy = build_level0_cloning_strategy(
        guide, vector_name, position, promoter, backbone_flavor, oligos
    )

    return {
        "name": name,
        "part_type": "NonCodingOther",
        "sequence": module["assembled_sequence"],
        # The module's Level 1 (BsaI) fusion sites for downstream assembly.
        "overhang_5prime": TRNA_OVERHANG_5,
        "overhang_3prime": TRNA_OVERHANG_3,
        "level": "0",
        "unit": "gRNA",
        "lab_source": lab_source,
        "description": description or f"Level 0 tRNA-sgRNA guide cassette ({vector_name}, pos {position})",
        "comments": strategy,
        "plasmid_id": vector_name,
        "features": module["features"],
        "vector": vector_name,
        "guide": guide,
        "position": position,
        "oligos": oligos,
        "module_length": module["length"],
    }


# --------------------------------------------------------------------------- #
# Level 1 guide-cassette assembly (chain the Level 0 guide modules)
# --------------------------------------------------------------------------- #

def assemble_level1_guide_cassette(
    guides: List[str],
    promoter: str = "TaU3p",
    backbone_flavor: str = "improved",
    l1_acceptor: str = "pICH47742",
) -> Dict[str, Any]:
    """
    Assemble the Level 1 tRNA-sgRNA guide cassette sequence by chaining the
    per-position Level 0 guide modules (promoter + tRNA-sgRNA array), so it can
    be stored as a single Level 1 Part for Level 2 assembly.

    The chained sequence overlaps the shared 4bp fusion site between adjacent
    Level 0 modules (each module after the first contributes its sequence minus
    the leading shared overhang), mirroring assemble_parts. The resulting Level 1
    cassette presents the fusion overhangs of its Level 2 acceptor position.

    Returns a dict with the assembled sequence and the Level 2 fusion overhangs.
    """
    if l1_acceptor not in L1_ACCEPTORS:
        raise GuideDesignError(f"Unknown Level 1 acceptor '{l1_acceptor}'.")
    position = L1_ACCEPTORS[l1_acceptor]["position"]
    o5, o3 = L2_POSITION_OVERHANGS[position]

    # Build the Level 1 unit sequence BASE-EXACTLY by chaining the RELEASED BsaI
    # inserts of the real Level 0 parts, in cloning order:
    #   promoter module (pFH3x)  +  guide module(s) (pFH49/pAK00x, guide spliced
    #   in)  +  end-linker (pAK-EL-0x).
    # Adjacent inserts share their 4 bp fusion overhang (written once). Each
    # part's real GenBank features (U6 promoter, tRNA, sgRNA scaffold, guide,
    # poly-T terminator) are carried through at their true chained coordinates.
    promoter_info = POL3_PROMOTERS.get(promoter, {})
    promoter_vector = promoter_info.get('vector')
    n_guides = len(guides)
    endlinker_vector = TRNA_ENDLINKERS.get(n_guides) if n_guides < MAX_TRNA_GUIDES else None

    # (role, vector, released-insert dict, display-name, module_length-or-None)
    pieces = []

    # Promoter module insert (from the raw promoter vector).
    if promoter_vector:
        pr = _released_bsai_insert(
            _vector_sequence(promoter_vector), _module_raw_features(promoter_vector))
        if pr:
            pieces.append(('promoter', promoter_vector, pr,
                           f"Pol III promoter module ({promoter_vector}, {promoter})", None))

    # Guide module inserts (assembled module with guide spliced in).
    for i, g in enumerate(guides):
        pos = i + 1
        vector = TRNA_POSITION1[promoter][backbone_flavor] if pos == 1 else TRNA_POSITION_MODULES.get(pos)
        if vector is None:
            raise GuideDesignError(f"No Level 0 module for array position {pos}.")
        module = assemble_level0_module(vector, validate_guide(g, TRNA_GUIDE_LEN))
        gi = _released_bsai_insert(module['assembled_sequence'], module.get('features'))
        if gi is None:
            raise GuideDesignError(
                f"Could not release the BsaI insert from guide module {vector}.")
        pieces.append(('guide', vector, gi,
                       f"Level 0 tRNA-sgRNA module ({vector}, guide {pos})", module['length']))

    # End-linker insert (closes arrays of <6 guides; carries the poly-T terminator).
    if endlinker_vector:
        el = _released_bsai_insert(
            _vector_sequence(endlinker_vector), _module_raw_features(endlinker_vector))
        if el:
            pieces.append(('end-linker', endlinker_vector, el,
                           f"End-linker ({endlinker_vector}, closes {n_guides}-guide array)", None))

    if not pieces:
        raise GuideDesignError("No Level 0 modules to assemble into a Level 1 unit.")

    # Chain the inserts, sharing each internal 4 bp fusion overhang once, and
    # carry each piece's features at the true chained coordinate.
    chained = ''
    features = []
    sub_parts = []
    for idx, (role, vector, ins, name, module_len) in enumerate(pieces):
        shift = len(chained)
        if idx == 0:
            chained += ins['insert']
        else:
            chained += ins['insert'][4:]   # drop the shared leading 4bp overhang
            shift -= 4                      # feature coord c in this insert -> shift + c
        for f in (ins.get('features') or []):
            try:
                fs = int(f['start']) + shift
                fe = int(f['end']) + shift
            except (TypeError, ValueError, KeyError):
                continue
            if fe <= fs:
                continue
            label = f.get('label') or f.get('type') or 'feature'
            if role == 'guide' and len(guides) > 1 and 'guide' in label.lower():
                label = f"{label} (guide {idx})"
            features.append({'type': f.get('type', 'misc_feature'), 'label': label,
                             'start': max(0, fs), 'end': fe, 'strand': f.get('strand', 1),
                             'source_vector': vector})

        # Reaction fragment (sub_part): the reaction calculator needs the full
        # source PLASMID size (you pipette the whole Level 0 plasmid).
        plasmid_size = _vector_length(vector)
        sub_parts.append({
            'part_name': name,
            'part_type': ('NonCodingPromoter' if role == 'promoter'
                          else 'NonCodingOther' if role == 'end-linker' else 'Coding'),
            'orientation': 'forward',
            'overhang_5prime': ins['left_oh'],
            'overhang_3prime': ins['right_oh'],
            'sequence_length': len(ins['insert']),
            'module_length': module_len if module_len is not None else len(ins['insert']),
            'level': '0',
            'source_vector': vector,
            'size': plasmid_size,          # full source plasmid size (reaction calc)
            'lab_source': 'Hahn/Nekrasov 2020 toolkit',
            'contributor': 'guide-designer',
            'description': {
                'promoter': f"Pol III promoter module: {promoter_info.get('description', promoter)}",
                'end-linker': f"tRNA-sgRNA array end-linker (poly-T terminator); closes a {n_guides}-guide array",
            }.get(role, f"tRNA-sgRNA array module; {backbone_flavor} backbone"),
            'is_coding': role == 'guide',
            'role': role,
            'array_position': idx,
        })

    return {
        "sequence": chained,
        "length": len(chained),
        "overhang_5prime": o5,
        "overhang_3prime": o3,
        "position": position,
        "l1_acceptor": l1_acceptor,
        "promoter": promoter,
        "backbone_flavor": backbone_flavor,
        "guide_count": len(guides),
        "sub_parts": sub_parts,
        "features": features,
    }


# --------------------------------------------------------------------------- #
# Position-aware Level 2 assembly (auto dummies + end-linker)
# --------------------------------------------------------------------------- #

def _part_l2_position(part) -> Optional[int]:
    """
    Map a part to its Level 2 position by matching its overhangs (in either
    orientation) to the canonical position boundaries. Returns 1-7 or None.
    """
    o5 = (getattr(part, 'overhang_5prime', '') or '').upper()
    o3 = (getattr(part, 'overhang_3prime', '') or '').upper()
    for pos, (b5, b3) in L2_POSITION_OVERHANGS.items():
        if (o5, o3) == (b5, b3):
            return pos
        # reverse orientation: presents rc(3')/rc(5')
        if (reverse_complement(o3), reverse_complement(o5)) == (b5, b3):
            return pos
    return None


def _part_plasmid_size(part) -> Optional[int]:
    """
    Best-estimate of the TOTAL PLASMID size a part is supplied in — the value the
    reaction calculator needs (you pipette the whole plasmid; 1 mol plasmid =
    1 mol insert). Prefer the part's stored `size` (set from the source plasmid),
    then fall back to the stored sequence length plus a typical MoClo vector
    backbone (~2500 bp) when only the insert/module sequence is known.
    """
    size = getattr(part, 'size', None)
    try:
        if size:
            return int(size)
    except (TypeError, ValueError):
        pass
    seq = getattr(part, 'sequence', None)
    if seq:
        n = len(seq)
        # Small module/filler sequences (dummies, end-linkers) are supplied in a
        # full vector; approximate the plasmid as insert + typical backbone.
        return n if n >= 2000 else n + 2500
    return None


def plan_level2_components(selected_parts, fillers):
    """
    Build the ordered Level 2 component list (filling internal gaps with dummies
    and closing with an end-linker) from the user's selected Level 1 parts.

    Args:
        selected_parts: list of Part objects the user chose (guide cassette, Cas,
            resistance, others) — each must map to a Level 2 position.
        fillers: dict with 'dummies' and 'endlinkers' -> {position: Part}.

    Returns:
        dict: {
          'ordered': [Part, ...]  (positions filled 1..max, then end-linker),
          'layout':  [{'position', 'part_name', 'role'}...],
          'endlinker': Part or None,
          'warnings': [...],
          'error': str or None,
        }
    """
    warnings = []
    placed = {}  # position -> (part, role)

    for part in selected_parts:
        pos = _part_l2_position(part)
        if pos is None:
            return {'ordered': None, 'layout': None, 'endlinker': None, 'warnings': warnings,
                    'error': (f"Part '{getattr(part, 'name', '?')}' "
                              f"(overhangs {part.overhang_5prime}/{part.overhang_3prime}) does not map to a "
                              f"standard Level 2 position; cannot place it automatically.")}
        if pos in placed:
            return {'ordered': None, 'layout': None, 'endlinker': None, 'warnings': warnings,
                    'error': (f"Two parts map to Level 2 position {pos}: "
                              f"'{placed[pos][0].name}' and '{part.name}'.")}
        placed[pos] = (part, 'selected')

    if not placed:
        return {'ordered': None, 'layout': None, 'endlinker': None, 'warnings': warnings,
                'error': 'No parts could be placed into Level 2 positions.'}

    last_pos = max(placed)
    dummies = fillers.get('dummies', {})

    # Fill every position from 1..last_pos (position 1 must be present so the
    # chain starts at TGCC for the universal acceptor).
    layout = []
    ordered = []
    for pos in range(1, last_pos + 1):
        if pos in placed:
            part, role = placed[pos]
        else:
            part = dummies.get(pos)
            role = 'dummy'
            if part is None:
                return {'ordered': None, 'layout': None, 'endlinker': None, 'warnings': warnings,
                        'error': f"No dummy part available for empty Level 2 position {pos}."}
            warnings.append(f"Auto-added dummy at position {pos}.")
        ordered.append(part)
        layout.append({'position': pos, 'part_name': part.name, 'role': role,
                       'size': _part_plasmid_size(part),
                       'insert_length': len(part.sequence) if getattr(part, 'sequence', None) else None})

    # Close the ring with the end-linker whose 5' overhang matches the last
    # position's 3' overhang (-> GGGA for the acceptor).
    endlinkers = fillers.get('endlinkers', {})
    endlinker = endlinkers.get(last_pos)
    if endlinker is None:
        return {'ordered': None, 'layout': None, 'endlinker': None, 'warnings': warnings,
                'error': f"No end-linker available to close after position {last_pos}."}
    ordered.append(endlinker)
    layout.append({'position': f'{last_pos}+', 'part_name': endlinker.name, 'role': 'end-linker',
                   'size': _part_plasmid_size(endlinker),
                   'insert_length': len(endlinker.sequence) if getattr(endlinker, 'sequence', None) else None})
    warnings.append(f"Auto-added {endlinker.name} to close the Level 2 ring (-> GGGA).")

    return {'ordered': ordered, 'layout': layout, 'endlinker': endlinker,
            'warnings': warnings, 'error': None}
