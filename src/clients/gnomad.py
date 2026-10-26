"""gnomAD GraphQL client (free, no key).

Used for gene-level confirmation and population context. Degrades gracefully if the
endpoint is slow/unavailable (it rate-limits aggressively) — callers note it as absent.
"""
from __future__ import annotations

from src.utils import http

API = "https://gnomad.broadinstitute.org/api"


def gene_info(symbol: str, reference: str = "GRCh38") -> dict:
    """Return {"available","gene": {...}} for a gene symbol."""
    query = """
    query Gene($symbol: String!, $ref: ReferenceGenomeId!) {
      gene(gene_symbol: $symbol, reference_genome: $ref) {
        gene_id
        symbol
        name
        chrom
      }
    }"""
    data = http.post_json(API, namespace="gnomad_gene",
                          json_body={"query": query,
                                     "variables": {"symbol": symbol, "ref": reference}})
    if not data or not data.get("data", {}).get("gene"):
        return {"available": False, "gene": None, "source": "gnomAD (GraphQL)"}
    return {"available": True, "gene": data["data"]["gene"], "source": "gnomAD (GraphQL)"}
