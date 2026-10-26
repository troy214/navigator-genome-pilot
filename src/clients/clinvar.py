"""ClinVar via NCBI E-utilities (free, no key).

esearch -> esummary. Returns structured records with source + a version/date note.
Distinguishes an absent record (no hits) from a benign record (hit with benign sig).
"""
from __future__ import annotations

from config import settings
from src.utils import http

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_COMMON = {"tool": settings.API_TOOL_NAME, "email": settings.API_CONTACT_EMAIL}


def query(gene: str, term: str | None = None, retmax: int = 3) -> dict:
    """Return {"available","present","records":[...],"source"} for a gene (+ optional term)."""
    q = f"{gene}[gene]"
    if term:
        q += f" AND {term}"
    es = http.get_json(ESEARCH, namespace="clinvar_esearch",
                       params={**_COMMON, "db": "clinvar", "term": q,
                               "retmode": "json", "retmax": retmax})
    if es is None:
        return {"available": False, "present": False, "records": [], "source": "ClinVar (NCBI)"}
    ids = es.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return {"available": True, "present": False, "records": [],
                "source": "ClinVar (NCBI E-utilities)",
                "note": "no ClinVar record found (absent, not benign)"}
    summ = http.get_json(ESUMMARY, namespace="clinvar_esummary",
                         params={**_COMMON, "db": "clinvar", "id": ",".join(ids),
                                 "retmode": "json"})
    records = []
    if summ:
        res = summ.get("result", {})
        for uid in res.get("uids", []):
            r = res.get(uid, {})
            germ = r.get("germline_classification", {}) or {}
            records.append({
                "uid": uid,
                "title": r.get("title"),
                "clinical_significance": germ.get("description") or r.get("clinical_significance", {}).get("description"),
                "last_evaluated": germ.get("last_evaluated"),
                "accession": r.get("accession"),
                "url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/",
            })
    return {"available": True, "present": True, "records": records,
            "source": "ClinVar (NCBI E-utilities)"}
