"""Orchestration for the Navigator genomic streaming data layer (Stages 01→06).

RESEARCH USE ONLY — part of a research tool for interpreting rare-disease genomes.
Outputs are ranked research hypotheses for researchers, NEVER a diagnosis and never
medical advice.

Chains the deterministic, non-LLM stages into one independently-callable entry point:

    01 ingest/normalize   src.pipeline.ingest  (bcftools norm -m- / pysam / line reader)
    02 QC & hard filters  src.pipeline.qc      (PASS, DP/GQ/AB, BED mask; missing→pass)
    03 columnar store     src.pipeline.store   (Parquet partitioned by chrom)
    04 index              src.pipeline.index   (bgzip+tabix region query; gene/rsID maps)
    05 annotate (join)    src.pipeline.annotate(gnomAD AF / ClinVar / phenotype panel)
    06 filter & rank      src.pipeline.rank    (the deterministic GATE, provenance-logged)

NON-BREAKING BY DESIGN:
  * ``run(case, config)`` is a standalone function — nothing imports it unless asked.
  * The optional stages (store/index) degrade: if ``pyarrow``/``pysam`` are missing they
    are skipped with a note, never crashing the run.
  * ``maybe_gate(case)`` is the ONLY integration hook. It returns the original case
    untouched unless ``settings.DATA_LAYER_GATE_ENABLED`` is set, in which case it returns
    a NEW ``CaseInput`` whose ``variants`` are the ranked candidate set and whose
    ``vcf_path`` is cleared — so the Intake agent (and the rest of the swarm) consume the
    pre-filtered variants through the existing interface with ZERO agent code changes.
    Default is OFF, so the current demo cases and verified behavior are unchanged.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from config import settings
from src.pipeline import qc, index as index_mod, annotate as annotate_mod, rank as rank_mod
from src.pipeline import vcf as vcf_mod
from src.utils.schema import CaseInput, Variant

log = logging.getLogger("navigator.data_layer")


# --------------------------------------------------------------------------- #
# Config + result
# --------------------------------------------------------------------------- #
@dataclass
class DataLayerConfig:
    qc_thresholds: qc.QCThresholds = field(default_factory=qc.QCThresholds)
    bed_path: str | None = None
    build_store: bool = True
    build_index: bool = True
    annotate: bool = True
    do_rank: bool = True
    store_dir: str | None = None
    phenotype_panel: set[str] | None = None
    annotation_sources: annotate_mod.AnnotationSources | None = None
    rank_config: rank_mod.RankConfig = field(default_factory=rank_mod.RankConfig)
    max_variants: int = 10000
    ref_fasta: str | None = None

    def resolved_store_dir(self) -> Path | None:
        if self.store_dir:
            return Path(self.store_dir)
        if settings.DATA_LAYER_STORE_DIR:
            return Path(settings.DATA_LAYER_STORE_DIR)
        return None  # store module uses its own DEFAULT_STORE_DIR


@dataclass
class DataLayerResult:
    case_id: str
    variants: list[Variant] = field(default_factory=list)  # final ranked candidate set
    qc_stats: qc.QCStats | None = None
    annotation_stats: annotate_mod.AnnotationStats | None = None
    store_path: Path | None = None
    index_gz: Path | None = None
    lookup_maps_path: Path | None = None
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"[data_layer {self.case_id}] "
                + "; ".join(self.notes) if self.notes else f"[data_layer {self.case_id}]")


# --------------------------------------------------------------------------- #
# Stage 01 line source + Variant enrichment
# --------------------------------------------------------------------------- #
def _resolve_vcf_path(case: CaseInput) -> Path | None:
    if not case.vcf_path:
        return None
    p = Path(case.vcf_path)
    if not p.is_absolute():
        p = settings.ROOT / case.vcf_path
    return p if p.exists() else None


def _stage01_data_lines(path: Path, ref_fasta: str | None) -> Iterator[str]:
    """Yield normalized (Stage 01) VCF data lines, falling back to a raw read.

    Mirrors the transparent selection in ``vcf.iter_variants``: use bcftools/pysam
    normalization when a tool is present, otherwise the dependency-free line reader.
    """
    try:
        from src.pipeline import ingest
        if ingest.tool_availability().any:
            try:
                yield from ingest.normalize_to_lines(path, ref_fasta=ref_fasta)
                return
            except ingest.NormalizationUnavailable as e:
                log.info("stage01 normalization unavailable (%s); raw read", e)
    except Exception as e:  # pragma: no cover - defensive
        log.warning("stage01 ingest layer unavailable (%s); raw read", e)
    # fallback: raw, gzip-aware line reader (data lines only)
    from src.pipeline.ingest import _open_text
    with _open_text(path) as fh:
        for line in fh:
            if line and not line.startswith("#"):
                yield line.rstrip("\n")


def _variant_with_meta(cols: list[str]) -> Variant | None:
    """Build a Variant from a VCF row AND enrich raw with QC/rank metadata.

    Reuses ``vcf._variant_from_cols`` for the base fields, then pulls consequence /
    impact (from ANN/CSQ), FILTER, and DP/GQ/GT (from FORMAT+sample) into ``raw`` so
    later stages have what they need without re-parsing.
    """
    v = vcf_mod._variant_from_cols(cols)
    if v is None:
        return None
    info = v.raw.get("info", {})
    ann = info.get("ANN") or info.get("CSQ")
    if ann:
        f = ann.split(",")[0].split("|")
        if len(f) > 1 and f[1]:
            v.raw["consequence"] = f[1]
        if len(f) > 2 and f[2]:
            v.raw["impact"] = f[2]
    if len(cols) > 6 and cols[6] not in ("", "."):
        v.raw["filter"] = cols[6]
    sample = qc.parse_sample_fields(cols)
    if "DP" in sample:
        try:
            v.raw["dp"] = int(sample["DP"])
        except ValueError:
            pass
    if "GQ" in sample:
        try:
            v.raw["gq"] = float(sample["GQ"])
        except ValueError:
            pass
    if "GT" in sample:
        v.raw["gt"] = sample["GT"]
    return v


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run(case: CaseInput, config: DataLayerConfig | None = None) -> DataLayerResult:
    """Run Stages 01→06 for a case and return the ranked candidate set + artifacts.

    Works whether the case carries a ``vcf_path`` (streamed through 01+02) or only
    structured ``variants`` (QC-on-lines is skipped; annotate+rank still apply).
    Optional stages degrade gracefully and never hard-crash the run.
    """
    config = config or DataLayerConfig()
    result = DataLayerResult(case_id=case.case_id)

    # ---- Stage 01 + 02: normalize + QC (only when we have a VCF of text lines) ----
    variants: list[Variant] = []
    vcf_path = _resolve_vcf_path(case)
    if vcf_path is not None:
        stats = qc.QCStats()
        bed = qc.BedMask.from_file(config.bed_path) if config.bed_path else None
        lines = _stage01_data_lines(vcf_path, config.ref_fasta)
        kept = qc.qc_filter_lines(lines, config.qc_thresholds, bed, stats)
        for line in kept:
            v = _variant_with_meta(line.split("\t"))
            if v is not None:
                v.raw["qc"] = {"passed": True}
                variants.append(v)
                if len(variants) >= config.max_variants:
                    break
        result.qc_stats = stats
        result.notes.append(stats.summary())
    else:
        # No VCF file: use structured variants as-is (already normalized upstream).
        variants = list(case.variants)
        result.notes.append(f"no vcf_path; using {len(variants)} structured variant(s)")

    # Merge any structured variants the case also carries (dedup by coordinate/gene+hgvs).
    if vcf_path is not None and case.variants:
        seen = {((v.chrom, v.pos, v.ref, v.alt) if v.pos else (v.gene, v.hgvs)) for v in variants}
        for v in case.variants:
            key = (v.chrom, v.pos, v.ref, v.alt) if v.pos else (v.gene, v.hgvs)
            if key not in seen:
                variants.append(v)
                seen.add(key)

    # ---- Stage 05: annotate (join) — do this before store so columns are populated ----
    if config.annotate:
        ann_stats = annotate_mod.AnnotationStats()
        panel = config.phenotype_panel
        if panel is None and case.hpo_terms:
            panel = None  # no offline HPO→gene panel bundled; stays stubbed unless provided
        annotate_mod.annotate_variants(
            variants, sources=config.annotation_sources,
            phenotype_panel=panel, stats=ann_stats)
        result.annotation_stats = ann_stats
        result.notes.append(ann_stats.summary())

    # ---- Stage 03: columnar store (optional; skip if pyarrow missing) ----
    if config.build_store and variants:
        try:
            from src.pipeline import store
            root = store.write_variants(variants, case.case_id,
                                        base_dir=config.resolved_store_dir())
            result.store_path = root
            result.notes.append(f"store: {root}")
        except Exception as e:  # StoreUnavailable or any write issue
            result.notes.append(f"store skipped ({e})")
            log.info("columnar store skipped: %s", e)

    # ---- Stage 04: index (optional; tabix needs pysam, maps always work) ----
    if config.build_index and variants:
        try:
            maps = index_mod.build_lookup_maps(variants)
            base = config.resolved_store_dir() or store_default_dir()
            maps_path = Path(base) / case.case_id / "lookup_maps.json"
            index_mod.save_lookup_maps(maps, maps_path)
            result.lookup_maps_path = maps_path
            result.notes.append(f"lookup_maps: {maps_path.name} ({maps['n']} variants)")
        except Exception as e:  # pragma: no cover - defensive
            result.notes.append(f"lookup maps skipped ({e})")
        if vcf_path is not None:
            try:
                base = config.resolved_store_dir() or store_default_dir()
                out_vcf = Path(base) / case.case_id / "normalized.vcf"
                out_vcf.parent.mkdir(parents=True, exist_ok=True)
                data_lines = []
                for v in variants:
                    if not v.pos:
                        continue
                    info = v.raw.get("info") or {}
                    info_str = ";".join(
                        k if val == "true" else f"{k}={val}" for k, val in info.items()
                    ) or "."
                    data_lines.append("\t".join([
                        v.chrom or ".", str(v.pos), v.rsid or ".",
                        v.ref or ".", v.alt or ".", ".",
                        v.raw.get("filter", "."), info_str,
                    ]))
                index_mod.write_sorted_vcf(data_lines, out_vcf)
                gz = index_mod.bgzip_and_tabix(out_vcf)
                result.index_gz = gz
                result.notes.append(f"tabix: {gz.name}")
            except index_mod.IndexUnavailable as e:
                result.notes.append(f"tabix skipped ({e})")
            except Exception as e:  # pragma: no cover - defensive
                result.notes.append(f"tabix skipped ({e})")

    # ---- Stage 06: filter & rank (the GATE) ----
    if config.do_rank:
        variants = rank_mod.rank_candidates(variants, case, config.rank_config)
        result.notes.append(f"ranked {len(variants)} candidate(s)")

    result.variants = variants
    log.info(result.summary())
    return result


def store_default_dir() -> Path:
    from src.pipeline import store
    return store.DEFAULT_STORE_DIR


# --------------------------------------------------------------------------- #
# The single, opt-in integration hook
# --------------------------------------------------------------------------- #
def maybe_gate(case: CaseInput, config: DataLayerConfig | None = None) -> CaseInput:
    """Return a gated CaseInput when enabled, else the original case unchanged.

    When ``settings.DATA_LAYER_GATE_ENABLED`` is truthy, runs the full data layer and
    returns a NEW ``CaseInput`` carrying the ranked candidate ``variants`` with
    ``vcf_path`` cleared — so the Intake agent consumes pre-filtered variants through
    the existing interface. Otherwise returns ``case`` untouched (default behavior).
    """
    if not settings.DATA_LAYER_GATE_ENABLED:
        return case
    try:
        res = run(case, config)
    except Exception as e:  # never let the gate break a run
        log.warning("data-layer gate failed (%s); passing case through unchanged", e)
        return case
    return CaseInput(
        case_id=case.case_id,
        variants=res.variants,
        clinical_summary=case.clinical_summary,
        hpo_terms=case.hpo_terms,
        vcf_path=None,  # variants are already parsed + ranked
    )
