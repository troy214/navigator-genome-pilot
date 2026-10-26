"""Europe PMC REST client (free, no key).

Returns publications with citations (PMID / DOI / URL) so every literature claim is sourced.
"""
from __future__ import annotations

from src.utils import http

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def search(query: str, page_size: int = 5) -> list[dict]:
    """Search Europe PMC; return a list of normalized publication dicts (may be empty)."""
    data = http.get_json(
        BASE, namespace="europepmc",
        params={"query": query, "format": "json", "pageSize": page_size, "resultType": "lite"},
    )
    if not data:
        return []
    out = []
    for r in data.get("resultList", {}).get("result", []):
        pmid = r.get("pmid")
        doi = r.get("doi")
        if pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            cite = f"PMID:{pmid}"
        elif doi:
            url = f"https://doi.org/{doi}"
            cite = f"DOI:{doi}"
        else:
            url = f"https://europepmc.org/article/{r.get('source','MED')}/{r.get('id','')}"
            cite = r.get("id", "europepmc")
        out.append({
            "citation": cite,
            "url": url,
            "title": r.get("title", "").rstrip("."),
            "authors": r.get("authorString", ""),
            "journal": r.get("journalTitle", ""),
            "year": r.get("pubYear", ""),
            "pmid": pmid,
            "doi": doi,
        })
    return out
