"""Stage 05 of the Navigator genomic streaming data layer: Annotate (join).

RESEARCH USE ONLY — part of a research tool for interpreting rare-disease genomes.
Outputs are hypotheses for researchers, never a diagnosis and never medical advice.

Deterministic, non-LLM join that enriches each candidate variant with the facts the
Filter & Rank gate (Stage 06) needs, drawing ONLY on the existing cached/API clients
(no bulk reference downloads):

  * population allele frequency   -> ``raw["gnomad_af"]`` (MyVariant.info / gnomAD)
  * clinical significance          -> ``raw["clinvar"]``   (MyVariant.info ClinVar / ClinVar E-utils)
  * in-silico score (CADD)         -> ``raw["cadd"]``      (reserved; see WIRED-VS-STUBBED below)
  * phenotype gene-panel membership-> ``raw["phenotype_match"]`` (True/False against a passed-in panel)

WIRED VS STUBBED (documented honestly, see also docs/DATA_LAYER_DESIGN.md):
  * gnomAD AF + ClinVar significance are WIRED through ``src.clients.myvariant`` (which
    aggregates ClinVar + gnomAD + dbNSFP) with ``src.clients.clinvar`` as a fallback.
    These are gene-scoped lookups against the free public APIs and the existing
    ``data/cache/`` layer — never a bulk download.
  * CADD / in-silico score is RESERVED: the column exists and is populated if a source
    hands us one, but we do NOT fetch CADD in bulk and the minimal MyVariant client does
    not currently surface a per-variant CADD, so in practice this stays null.
  * The phenotype gene panel is STUBBED: there is no offline gene↔phenotype panel source
    bundled here, so membership is computed against a caller-supplied set of gene symbols
    (e.g. derived upstream from the case's HPO terms). Pass ``phenotype_panel=None`` to skip.

DEGRADES GRACEFULLY / OFFLINE: every network call is wrapped — any failure (or the http
layer being stubbed to return nothing in tests) leaves the column null and records the
source as unavailable, never raising. Sources are injected (:class:`AnnotationSources`)
so unit tests run fully offline with canned stubs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Iterable

from src.utils.schema import Variant

log = logging.getLogger("navigator.annotate")


# --------------------------------------------------------------------------- #
# Injectable sources (default to the real, cache-backed clients)
# --------------------------------------------------------------------------- #
@dataclass
class AnnotationSources:
    """Pluggable annotation lookups. ``None`` members fall back to the real clients.

    Each callable mirrors the existing client signature and must never raise — the
    real clients already return a dict with ``available`` and degrade to
    ``available=False`` when the network/cache has nothing. Tests inject stubs here.
    """
    # (gene, term=None) -> {"available","hits":[{"gnomad_af","clinical_significance",...}]}
    myvariant_query: Callable[..., dict] | None = None
    # (gene, term=None) -> {"available","present","records":[{"clinical_significance",...}]}
    clinvar_query: Callable[..., dict] | None = None

    def resolved(self) -> "AnnotationSources":
        mv = self.myvariant_query
        cv = self.clinvar_query
        if mv is None:
            from src.clients import myvariant
            mv = myvariant.query_gene_variant
        if cv is None:
            from src.clients import clinvar
            cv = clinvar.query
        return AnnotationSources(myvariant_query=mv, clinvar_query=cv)


@dataclass
class AnnotationStats:
    """Provenance for the annotation stage."""
    total: int = 0
    gnomad_af_filled: int = 0
    clinvar_filled: int = 0
    phenotype_matched: int = 0
    sources_unavailable: set[str] = field(default_factory=set)

    def summary(self) -> str:
        unavail = (", ".join(sorted(self.sources_unavailable))
                   if self.sources_unavailable else "none")
        return (f"annotated {self.total} variant(s): "
                f"gnomad_af+{self.gnomad_af_filled}, clinvar+{self.clinvar_filled}, "
                f"phenotype+{self.phenotype_matched}; sources unavailable: {unavail}")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _match_hit(variant: Variant, hits: list[dict]) -> dict | None:
    """Pick the best hit for a variant: prefer rsID / HGVS match, else first hit."""
    if not hits:
        return None
    if variant.rsid:
        for h in hits:
            if h.get("rsid") and str(h["rsid"]) == str(variant.rsid):
                return h
    if variant.hgvs:
        for h in hits:
            if h.get("hgvs") and variant.hgvs in str(h["hgvs"]):
                return h
    return hits[0]  # gene-level context fallback


def _annotate_one(v: Variant, src: AnnotationSources,
                  panel: set[str] | None, stats: AnnotationStats) -> None:
    stats.total += 1

    # ---- phenotype gene-panel membership (STUBBED: caller-supplied panel) ----
    if panel is not None:
        match = bool(v.gene and v.gene in panel)
        v.raw["phenotype_match"] = match
        if match:
            stats.phenotype_matched += 1

    if not v.gene:
        return  # nothing to look up without a gene symbol

    # ---- MyVariant.info: gnomAD AF + ClinVar significance (WIRED) ----
    try:
        res = src.myvariant_query(v.gene)
    except Exception as e:  # defensive: clients shouldn't raise, but never crash the layer
        log.warning("myvariant lookup failed for %s: %s", v.gene, e)
        res = {"available": False, "hits": []}
    if not res.get("available"):
        stats.sources_unavailable.add("MyVariant.info")
    else:
        hit = _match_hit(v, res.get("hits", []))
        if hit:
            if v.raw.get("gnomad_af") is None and v.allele_freq is None \
                    and hit.get("gnomad_af") is not None:
                v.raw["gnomad_af"] = hit["gnomad_af"]
                stats.gnomad_af_filled += 1
            if v.raw.get("clinvar") is None and hit.get("clinical_significance"):
                v.raw["clinvar"] = hit["clinical_significance"]
                stats.clinvar_filled += 1
            # CADD reserved: populate only if a source ever provides it
            if v.raw.get("cadd") is None and hit.get("cadd") is not None:
                v.raw["cadd"] = hit["cadd"]

    # ---- ClinVar E-utilities fallback (WIRED) if significance still unknown ----
    if v.raw.get("clinvar") is None:
        try:
            cv = src.clinvar_query(v.gene)
        except Exception as e:
            log.warning("clinvar lookup failed for %s: %s", v.gene, e)
            cv = {"available": False, "records": []}
        if not cv.get("available"):
            stats.sources_unavailable.add("ClinVar (NCBI)")
        else:
            for rec in cv.get("records", []):
                if rec.get("clinical_significance"):
                    v.raw["clinvar"] = rec["clinical_significance"]
                    stats.clinvar_filled += 1
                    break


# --------------------------------------------------------------------------- #
# Public entry
# --------------------------------------------------------------------------- #
def annotate_variants(variants: Iterable[Variant], *,
                      sources: AnnotationSources | None = None,
                      phenotype_panel: Iterable[str] | None = None,
                      stats: AnnotationStats | None = None) -> list[Variant]:
    """Enrich variants in place (and return them) with AF / ClinVar / phenotype joins.

    ``sources`` lets tests inject offline stubs; by default the real cache-backed
    clients are used. ``phenotype_panel`` is a set of gene symbols (stubbed panel);
    when provided, ``raw["phenotype_match"]`` is set per variant. Never raises on a
    source failure — the column is simply left null and noted in ``stats``.
    """
    variants = list(variants)
    src = (sources or AnnotationSources()).resolved()
    panel = set(phenotype_panel) if phenotype_panel is not None else None
    stats = stats if stats is not None else AnnotationStats()
    for v in variants:
        _annotate_one(v, src, panel, stats)
    log.info(stats.summary())
    return variants
