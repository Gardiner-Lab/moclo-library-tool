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
    Search Addgene to find the catalog number for a plasmid name.
    """
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
