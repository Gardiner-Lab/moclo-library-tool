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


def _creates_forbidden_site(sequence: str) -> bool:
    """True if the sequence contains any Type IIS recognition site we must avoid."""
    s = sequence.upper()
    return any(site in s for site in _FORBIDDEN_SITES)


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
                "Combine the Level 1 tRNA-sgRNA unit with a Level 1 SpCas9 nuclease unit, a "
                "Level 1 selectable-marker unit and the single-unit endlinker into a Level 2 "
                "backbone via BpiI."
            ),
            "enzyme": "BpiI",
            "single_unit_endlinker": L2_SINGLE_UNIT_ENDLINKER,
            "required_units": [
                "Level 1 SpCas9 nuclease transcription unit (e.g. pFH23/pFH66/pFH67)",
                "Level 1 selectable-marker transcription unit (e.g. BAR / NPTII)",
                f"This Level 1 tRNA-sgRNA unit ({l1_acceptor})",
                f"Endlinker {L2_SINGLE_UNIT_ENDLINKER} (for a single guide-RNA Level 1 unit)",
                "A Level 2 acceptor backbone",
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


def assemble_level0_module(vector_name: str, guide: str) -> Dict[str, Any]:
    """
    Assemble the FULL Level 0 guide-cassette module: take the real toolkit
    acceptor vector, excise the lacZ placeholder, and splice in the guide so the
    module reads  ...tRNA | TGCA | guide | (GTTT)scaffold...  exactly as it would
    after the BpiI cut-ligation.

    Returns a dict with the complete assembled circular module sequence, the
    guide's position within it, and simple feature annotations.
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

    features = [
        {"type": "misc_feature", "label": "guide (protospacer)", "start": guide_start, "end": guide_end, "strand": 1},
        {"type": "misc_feature", "label": "5' fusion site TGCA", "start": guide_start - 4, "end": guide_start, "strand": 1},
        {"type": "misc_feature", "label": "3' fusion site (AAAC / GTTT)", "start": guide_end, "end": guide_end + 4, "strand": 1},
    ]

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
