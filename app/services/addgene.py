"""
Addgene lookup service.

Fetches descriptive names (Gene/Insert name) from Addgene for MoClo parts
based on their plasmid ID (e.g. pICSL50013, pICH41421).

Strategy:
1. Search Addgene for the plasmid name to find the catalog number
2. Fetch the plasmid page
3. Extract the "Gene/Insert name" field

This runs during part upload to enrich the description field.
"""

import re
import logging
from typing import Optional, Dict
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# Cache to avoid repeated lookups for the same plasmid
_addgene_cache: Dict[str, Optional[str]] = {}

# Known MoClo plasmid name patterns (TSL/ENSA toolkit)
MOCLO_PATTERN = re.compile(r'^pI(CSL|CH|AGM)\d+', re.IGNORECASE)

# Request headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; MoClo-Library-Tool/1.0; Academic research)',
    'Accept': 'text/html,application/xhtml+xml'
}


def lookup_addgene_name(plasmid_name: str) -> Optional[str]:
    """
    Look up the Gene/Insert name from Addgene for a given plasmid.

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

    try:
        gene_name = _do_lookup(plasmid_name)
        _addgene_cache[plasmid_name] = gene_name
        if gene_name:
            logger.info(f"Addgene lookup for {plasmid_name}: {gene_name}")
        else:
            logger.debug(f"Addgene lookup for {plasmid_name}: not found")
        return gene_name
    except Exception as e:
        logger.warning(f"Addgene lookup failed for {plasmid_name}: {e}")
        _addgene_cache[plasmid_name] = None
        return None


def _do_lookup(plasmid_name: str) -> Optional[str]:
    """
    Perform the actual Addgene lookup.

    Step 1: Search Addgene to find the catalog number
    Step 2: Fetch the plasmid page and extract Gene/Insert name
    """
    catalog_number = _find_catalog_number(plasmid_name)
    if not catalog_number:
        return None
    return _fetch_gene_insert_name(catalog_number)


def _find_catalog_number(plasmid_name: str) -> Optional[str]:
    """
    Find the Addgene catalog number for a plasmid name.
    Uses a static mapping for known MoClo toolkit plasmids,
    then falls back to searching Addgene if not in the map.
    """
    # Static mapping of known MoClo toolkit plasmids to Addgene catalog numbers
    KNOWN_CATALOG = {
        "pICH44157": "50258", "pICH44179": "50290", "pICH44188": "50289",
        "pICH44199": "50286", "pAGM1467": "50298", "pAGM1479": "50291",
        "pAGM1482": "50295", "pAGM5331": "50294", "pAGM5343": "50297",
        "pAGM5355": "50296", "pAGT707": "51835", "pICH37431": "50306",
        "pICH41373": "50252", "pICH41388": "50253", "pICH41402": "50285",
        "pICH41414": "50337", "pICH41421": "50339", "pICH41432": "50343",
        "pICH41531": "50321", "pICSL50013": "50312", "pICSL80005": "50322",
        "pICSL50004": "50316", "pICSL50009": "50309", "pICH47732": "48000",
        "pICH47742": "48001", "pICH47751": "48002", "pICH47761": "48003",
        "pICH47772": "48004", "pICH47781": "48005", "pICH47802": "48007",
        "pICH47811": "48008", "pICH47822": "48009", "pICH47831": "48010",
        "pICH47841": "48011", "pICH47851": "48012", "pICH47861": "48013",
        "pAGM4723": "48015", "pICH44300": "50340", "pICH77911": "50342",
        "pICH77901": "50341", "pICH71411": "50345", "pICH71431": "50344",
        "pICSL00001": "50346", "pICSL00002": "50347",
        "pICH37326": "50305",
        # MoClo Plant Parts Kit (Patron lab)
        "pICSL01009": "47998", "pICSL11024": "50269", "pICSL12008": "50270",
        "pICSL12009": "68257", "pICSL12015": "50271", "pICSL12019": "50272",
        "pICSL13001": "50266", "pICSL13002": "50267", "pICSL13004": "50268",
        "pICSL13008": "50265", "pICSL20005": "50273", "pICSL20009": "50274",
        "pICSL20012": "50275", "pICSL30003": "50276", "pICSL30006": "50277",
        "pICSL30007": "50278", "pICSL30008": "50279", "pICSL30009": "50280",
        "pICSL30014": "50281", "pICSL40001": "50283", "pICSL40002": "50284",
        "pICSL50001": "50307", "pICSL50002": "50315", "pICSL50003": "50308",
        "pICSL50005": "50310", "pICSL50006": "50317", "pICSL50007": "50318",
        "pICSL50008": "50313", "pICSL50010": "50319", "pICSL50014": "50311",
        "pICSL50015": "50320", "pICSL60002": "50323", "pICSL60004": "50324",
        "pICSL60006": "50325", "pICSL60008": "50326", "pICSL70001": "50327",
        "pICSL70004": "50328", "pICSL70008": "50329", "pICSL70010": "50330",
        "pICSL70012": "50331", "pICSL80001": "50332", "pICSL80002": "50333",
        "pICSL80003": "50334", "pICSL80004": "50335", "pICSL80006": "50336",
        "pICSL80007": "50314",
    }

    # Check static map first (case-sensitive)
    if plasmid_name in KNOWN_CATALOG:
        return KNOWN_CATALOG[plasmid_name]

    # Try case-insensitive match
    for known_name, cat_num in KNOWN_CATALOG.items():
        if known_name.lower() == plasmid_name.lower():
            return cat_num

    # Fallback: try HTTP search (may not work on all servers due to JS rendering)
    search_url = (
        "https://www.addgene.org/search/catalog/plasmids/?q=" + plasmid_name
    )

    try:
        req = Request(search_url, headers=HEADERS)
        with urlopen(req, timeout=15) as response:
            final_url = response.url
            redirect_match = re.search(r'addgene\.org/(\d+)/', final_url)
            if redirect_match:
                return redirect_match.group(1)

            html = response.read().decode('utf-8', errors='ignore')

            escaped_name = re.escape(plasmid_name)
            pattern = r'href="/(\d{4,6})/"[^>]*>[^<]*' + escaped_name
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)

            name_pos = html.lower().find(plasmid_name.lower())
            if name_pos > 0:
                window = html[max(0, name_pos - 500):name_pos + 500]
                catalog_matches = re.findall(r'href="/(\d{4,6})/"', window)
                if catalog_matches:
                    return catalog_matches[0]

            all_catalog = re.findall(r'href="/(\d{4,6})/"', html)
            if all_catalog:
                return all_catalog[0]

    except (HTTPError, URLError, TimeoutError) as e:
        logger.debug(f"Search failed for {plasmid_name}: {e}")

    return None


def _fetch_gene_insert_name(catalog_number: str) -> Optional[str]:
    """
    Fetch the Addgene plasmid page and extract the Gene/Insert name.
    """
    url = f"https://www.addgene.org/{catalog_number}/"

    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')

            patterns = [
                r'Gene/Insert\s+name[:\s]*:?\s*([^\n<]+)',
                r'Gene/Insert name</[^>]+>\s*:?\s*<[^>]+>([^<]+)',
                r'"insert_gene_name"[^>]*>([^<]+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    name = re.sub(r'<[^>]+>', '', name)
                    name = re.sub(r'&[a-z]+;', ' ', name)
                    name = re.sub(r'\s+', ' ', name).strip()
                    if name and len(name) > 1 and name.lower() not in (
                        'none', 'n/a', '', 'gene/insert'
                    ):
                        return name

    except (HTTPError, URLError, TimeoutError) as e:
        logger.debug(f"Failed to fetch Addgene page {catalog_number}: {e}")

    return None


def clear_cache():
    """Clear the Addgene lookup cache."""
    global _addgene_cache
    _addgene_cache = {}
