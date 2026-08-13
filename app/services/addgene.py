"""
Addgene lookup service.

Provides descriptive Gene/Insert names for MoClo toolkit plasmids.
Data sourced from Addgene (addgene.org) for the Engler et al. and
Patron et al. MoClo toolkit collections.

Since Addgene pages require JavaScript rendering, Gene/Insert names
are stored as a static mapping. New plasmids can be added to the
GENE_INSERT_NAMES dictionary below.
"""

import re
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Cache to avoid repeated lookups for the same plasmid
_addgene_cache: Dict[str, Optional[str]] = {}

# Known MoClo plasmid name patterns (TSL/ENSA toolkit)
MOCLO_PATTERN = re.compile(r'^p(I(CSL|CH)|AGM|AGT)\d+', re.IGNORECASE)

# Hardcoded Gene/Insert names from Addgene for known MoClo toolkit plasmids.
# Addgene pages require JavaScript rendering, so we store these directly.
GENE_INSERT_NAMES = {
    # MoClo Toolkit (Marillonnet lab) - promoters, UTRs, signal peptides, etc.
    "pICH44157": "promoter, RbcS2B (AT5g38420, A. thaliana)",
    "pICH44179": "5' UTR, RbcS2B (AT5g38420, A. thaliana)",
    "pICH44188": "5'UTR BSMV (Barley Stripe Mosaic Virus)",
    "pICH44199": "5'UTR, omega (Potato Virus X)",
    "pAGM1467": "5'UTR, omega (TMV) + HIS tag + enterokinase cleavage site",
    "pAGM1479": "5'UTR, omega (TMV) + N terminal HIS tag (6x polyhistidine)",
    "pAGM1482": "5'UTR, omega (TMV) + mitochondrial localisation signal ScCoxIV",
    "pAGM5331": "5'UTR, omega (TMV) + nuclear localisation signal (SV40)",
    "pAGM5343": "5'UTR, omega (TMV) + signal peptide, RAmy3A (O. sativa) + HIS tag",
    "pAGM5355": "5'UTR, omega (TMV) + chloroplast transit peptide, RbcS (synthetic) + HIS tag",
    "pAGT707": "Tomato Mosaic virus 5'UTR + CCAT",
    "pICH37431": "signal peptide, RAmy3A (O. sativa)",
    "pICH41373": "promoter (1.3 kb), 35s (CaMV)",
    "pICH41388": "promoter (0.4 kb), 35s (CaMV)",
    "pICH41402": "5'UTR, omega (Tobacco Mosaic Virus)",
    "pICH41414": "3'UTR/terminator, 35s (CaMV)",
    "pICH41421": "3'UTR/terminator, nos (A. tumefaciens)",
    "pICH41432": "3'UTR/terminator, ocs (A. tumefaciens)",
    "pICH41531": "CDS, GFP (A. victoria)",
    "pICH44300": "3'UTR/terminator, act2 (A. thaliana)",
    "pICH77911": "3'UTR/terminator, ags (A. tumefaciens)",
    "pICH77901": "3'UTR/terminator, mas (A. tumefaciens)",
    "pICH71411": "3'UTR/terminator, RbcS3C (S. lycopersicum)",
    "pICH71431": "3'UTR/terminator, ATPase (S. lycopersicum)",
    # MoClo Plant Parts Kit (Patron lab) - coding sequences, tags, reporters
    "pICSL50013": "C terminal T7 tag (bacteriophage T7 gene 10)",
    "pICSL80005": "CDS, turboGFP codon-optimised for plants (P. plumata)",
    "pICSL50004": "CDS, mCherry variant of RFP (Discosoma sp.)",
    "pICSL50009": "C terminal HA tag (6x Human influenza hemagglutinin)",
    "pICSL50001": "CDS, GUS (E. coli)",
    "pICSL50002": "CDS, GUSPlus (Staphylococcus sp.)",
    "pICSL50003": "CDS, GFP5 (A. victoria)",
    "pICSL50005": "CDS, luciferase (Photinus pyralis)",
    "pICSL50006": "CDS, DsRed (Discosoma sp.)",
    "pICSL50007": "CDS, Renilla luciferase (Renilla reniformis)",
    "pICSL50008": "CDS, YFP (A. victoria)",
    "pICSL50010": "CDS, CFP (A. victoria)",
    "pICSL50014": "C terminal cMyc tag",
    "pICSL50015": "C terminal FLAG tag",
    "pICSL80001": "CDS, aadA spectinomycin resistance (E. coli)",
    "pICSL80002": "CDS, nptII kanamycin resistance (E. coli)",
    "pICSL80003": "CDS, hpt hygromycin resistance (E. coli)",
    "pICSL80004": "CDS, bar Basta resistance (S. hygroscopicus)",
    "pICSL80006": "CDS, pat phosphinothricin resistance",
    "pICSL80007": "CDS, mRFP1 (Discosoma sp.)",
    "pICSL60002": "CDS no stop, GFP5 (A. victoria)",
    "pICSL60004": "CDS no stop, mCherry (Discosoma sp.)",
    "pICSL60006": "CDS no stop, YFP (A. victoria)",
    "pICSL60008": "CDS no stop, CFP (A. victoria)",
    "pICSL70001": "N terminal signal peptide, PR1a (N. tabacum)",
    "pICSL70004": "N terminal chloroplast transit peptide, RbcS (P. sativum)",
    "pICSL70008": "N terminal mitochondrial targeting, ScCoxIV (S. cerevisiae)",
    "pICSL70010": "N terminal nuclear localisation signal, SV40",
    "pICSL70012": "N terminal ER retention signal, HDEL",
    "pICSL11024": "promoter, nos (A. tumefaciens)",
    "pICSL12008": "promoter, mas (A. tumefaciens)",
    "pICSL12009": "promoter, AtUBQ10 (A. thaliana)",
    "pICSL12015": "promoter, OsAct1 (O. sativa)",
    "pICSL12019": "promoter, ZmUbi1 (Z. mays)",
    "pICSL13001": "5'UTR + intron, AtUBQ10 (A. thaliana)",
    "pICSL13002": "5'UTR + intron, OsAct1 (O. sativa)",
    "pICSL13004": "5'UTR + intron, ZmUbi1 (Z. mays)",
    "pICSL13008": "5'UTR, CaMV 35S omega (TMV)",
    "pICSL20005": "signal peptide, pathogenesis-related protein 1a (N. tabacum)",
    "pICSL20009": "transit peptide, RbcS (P. sativum)",
    "pICSL20012": "mitochondrial targeting, ScCoxIV (S. cerevisiae)",
    "pICSL30003": "3'UTR/terminator, nos (A. tumefaciens)",
    "pICSL30006": "3'UTR/terminator, ocs (A. tumefaciens)",
    "pICSL30007": "3'UTR/terminator, 35S (CaMV)",
    "pICSL30008": "3'UTR/terminator, mas (A. tumefaciens)",
    "pICSL30009": "3'UTR/terminator, act2 (A. thaliana)",
    "pICSL30014": "3'UTR/terminator, RbcS (S. lycopersicum)",
    "pICSL40001": "CDS, nptII kanamycin resistance (E. coli)",
    "pICSL40002": "CDS, bar Basta resistance (S. hygroscopicus)",
    "pICSL01009": "acceptor module, position 1",
    "pICSL00001": "end-linker, position 1-2",
    "pICSL00002": "end-linker, position 2-3",
    "pICH37326": "CDS no stop, mEOS2 photoactivatable fluorescent protein",
}


def lookup_addgene_name(plasmid_name: str) -> Optional[str]:
    """
    Look up the Gene/Insert name from Addgene for a given plasmid.

    Uses a hardcoded mapping of known MoClo toolkit plasmids since
    Addgene pages require JavaScript rendering that urllib cannot handle.

    Args:
        plasmid_name: The plasmid identifier (e.g. "pICSL50013")

    Returns:
        The Gene/Insert name if found, None otherwise.
    """
    if not plasmid_name:
        return None

    # Check cache first
    if plasmid_name in _addgene_cache:
        return _addgene_cache[plasmid_name]

    # Only look up names that match MoClo plasmid patterns
    if not MOCLO_PATTERN.match(plasmid_name):
        return None

    # Look up in the known Gene/Insert names mapping
    gene_name = GENE_INSERT_NAMES.get(plasmid_name)
    if not gene_name:
        # Try case-insensitive
        for known_name, name_val in GENE_INSERT_NAMES.items():
            if known_name.lower() == plasmid_name.lower():
                gene_name = name_val
                break

    _addgene_cache[plasmid_name] = gene_name
    if gene_name:
        logger.info(f"Addgene lookup for {plasmid_name}: {gene_name}")
    return gene_name


def clear_cache():
    """Clear the Addgene lookup cache."""
    global _addgene_cache
    _addgene_cache = {}
