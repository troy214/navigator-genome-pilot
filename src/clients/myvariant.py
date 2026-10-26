"""MyVariant.info client (free, no key).

Aggregates ClinVar + gnomAD + dbNSFP. Practical single-call source for a variant's
clinical significance and population frequency. We distinguish "absent" from "benign".
"""
from __future__ import annotations

from src.utils import http

BASE = "https://myvariant.info/v1"


def query_gene_variant(gene: str, term: str | None = None, size: int = 3) -> dict:
    """Query by gene (+ optional free text) for clinically significant records.

    Returns {"available": bool, "hits": [...], "source": "MyVariant.info"}.
    """
    q = f"clinvar.gene.symbol:{gene}"
    if term:
        q += f" AND {term}"
    data = http.get_json(
        f"{BASE}/query", namespace="myvariant",
        params={"q": q, "size": size,
                "fields": "clinvar,gnomad_genome,gnomad_exome,dbnsfp,snpeff"},
    )
    if data is None:
        return {"available": False, "hits": [], "source": "MyVariant.info"}
    hits = []
    for h in data.get("hits", []):
        cv = h.get("clinvar") or {}
        rcv = cv.get("rcv")
        sig = None
        if isinstance(rcv, list) and rcv:
            sig = rcv[0].get("clinical_significance")
        elif isinstance(rcv, dict):
            sig = rcv.get("clinical_significance")
        gad = h.get("gnomad_genome") or h.get("gnomad_exome") or {}
        af = (gad.get("af") or {}).get("af") if isinstance(gad.get("af"), dict) else gad.get("af")
        hits.append({
            "id": h.get("_id"),
            "rsid": (cv.get("rsid") or (cv.get("gene") or {}).get("rsid")),
            "clinical_significance": sig,
            "gnomad_af": af,
            "hgvs": (cv.get("hgvs") or {}).get("coding") if isinstance(cv.get("hgvs"), dict) else None,
        })
    return {
        "available": True,
        "total": data.get("total", 0),
        "hits": hits,
        "source": "MyVariant.info (ClinVar/gnomAD/dbNSFP)",
    }
