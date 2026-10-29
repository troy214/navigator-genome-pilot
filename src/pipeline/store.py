"""Stage 03 of the Navigator genomic streaming data layer: Columnar Store.

RESEARCH USE ONLY — part of a research tool for interpreting rare-disease genomes.
Outputs are hypotheses for researchers, never a diagnosis and never medical advice.

Persist the normalized + QC'd variants ONCE to Parquet (via pyarrow), partitioned by
chromosome, so later stages and agents do vectorized, columnar scans with predicate
push-down and column projection instead of re-parsing VCF text. This is deterministic,
non-LLM infrastructure.

Layout (configurable base dir):
    data/variant_store/<case_id>/chrom=<chrom>/part-0.parquet

Columns (nulls where unknown):
    chrom, pos, ref, alt, gene, consequence, gnomad_af, clinvar, cadd, gt, dp, gq
plus useful extras: rsid, hgvs, impact, filter.

Non-breaking / optional: if ``pyarrow`` is not installed, :func:`write_variants`
raises :class:`StoreUnavailable`; the orchestrator treats the columnar store as an
optional artifact and continues.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from config import settings
from src.utils.schema import Variant

log = logging.getLogger("navigator.store")

# Required columns (the design-doc set) + extras that cost nothing and help agents.
STORE_COLUMNS = [
    "chrom", "pos", "ref", "alt", "gene", "consequence",
    "gnomad_af", "clinvar", "cadd", "gt", "dp", "gq",
    "rsid", "hgvs", "impact", "filter",
]

DEFAULT_STORE_DIR = settings.DATA_DIR / "variant_store"


class StoreUnavailable(RuntimeError):
    """Raised when pyarrow is not installed so the caller can skip the store."""


def pyarrow_version() -> str | None:
    try:
        import pyarrow  # noqa: F401
        return pyarrow.__version__
    except Exception:
        return None


def _get(v: Variant, key: str) -> Any:
    """Read a store column from a Variant, consulting ``raw`` for layer metadata."""
    if key == "chrom":
        return v.chrom
    if key == "pos":
        return v.pos
    if key == "ref":
        return v.ref
    if key == "alt":
        return v.alt
    if key == "gene":
        return v.gene
    if key == "rsid":
        return v.rsid
    if key == "hgvs":
        return v.hgvs
    if key == "gnomad_af":
        # prefer an explicit annotated value, else the VCF allele_freq
        return v.raw.get("gnomad_af", v.allele_freq)
    # everything else lives in raw (consequence/impact/filter/clinvar/cadd/gt/dp/gq)
    return v.raw.get(key)


def variant_to_row(v: Variant) -> dict[str, Any]:
    """Project a Variant (+ its raw layer metadata) onto the store schema."""
    row = {c: _get(v, c) for c in STORE_COLUMNS}
    # normalize types a little so Arrow infers a stable schema
    if row["chrom"] is not None:
        row["chrom"] = str(row["chrom"])
    for intcol in ("pos", "dp"):
        if row[intcol] is not None:
            try:
                row[intcol] = int(row[intcol])
            except (TypeError, ValueError):
                row[intcol] = None
    for fltcol in ("gnomad_af", "cadd", "gq"):
        if row[fltcol] is not None:
            try:
                row[fltcol] = float(row[fltcol])
            except (TypeError, ValueError):
                row[fltcol] = None
    return row


def _build_table(variants: list[Variant]):
    import pyarrow as pa
    # explicit schema keeps columns + types stable even when every value is null
    schema = pa.schema([
        ("chrom", pa.string()), ("pos", pa.int64()),
        ("ref", pa.string()), ("alt", pa.string()),
        ("gene", pa.string()), ("consequence", pa.string()),
        ("gnomad_af", pa.float64()), ("clinvar", pa.string()),
        ("cadd", pa.float64()), ("gt", pa.string()),
        ("dp", pa.int64()), ("gq", pa.float64()),
        ("rsid", pa.string()), ("hgvs", pa.string()),
        ("impact", pa.string()), ("filter", pa.string()),
    ])
    rows = [variant_to_row(v) for v in variants]
    cols = {name: [r[name] for r in rows] for name in STORE_COLUMNS}
    return pa.Table.from_pydict(cols, schema=schema)


def write_variants(variants: Iterable[Variant], case_id: str,
                   base_dir: str | Path | None = None,
                   overwrite: bool = True) -> Path:
    """Write variants to a per-case Parquet dataset partitioned by chromosome.

    Returns the dataset root (``<base_dir>/<case_id>``). Raises
    :class:`StoreUnavailable` if pyarrow is missing.
    """
    if pyarrow_version() is None:
        raise StoreUnavailable("pyarrow is not installed")
    import pyarrow.dataset as ds

    variants = list(variants)
    base = Path(base_dir) if base_dir else DEFAULT_STORE_DIR
    root = base / case_id
    if overwrite and root.exists():
        import shutil
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    table = _build_table(variants)
    # partition by chrom -> chrom=<value>/ subdirs; vectorized predicate push-down on read
    ds.write_dataset(
        table, root, format="parquet",
        partitioning=["chrom"], partitioning_flavor="hive",
        existing_data_behavior="overwrite_or_ignore",
    )
    log.info("wrote %d variant(s) to columnar store %s (partitioned by chrom)",
             len(variants), root)
    return root


def read_variants(case_id: str, base_dir: str | Path | None = None, *,
                  columns: list[str] | None = None,
                  chrom: str | None = None,
                  max_gnomad_af: float | None = None) -> list[dict[str, Any]]:
    """Read back rows with column projection + predicate push-down.

    ``columns`` projects a subset; ``chrom`` / ``max_gnomad_af`` push filters down
    into the Parquet scan instead of re-parsing text or loading everything.
    """
    if pyarrow_version() is None:
        raise StoreUnavailable("pyarrow is not installed")
    import pyarrow.dataset as ds

    import pyarrow as pa
    base = Path(base_dir) if base_dir else DEFAULT_STORE_DIR
    root = base / case_id
    if not root.exists():
        return []
    # Force the chrom partition column to string (hive auto-inference would type a
    # numeric-looking chrom like "7" as int, breaking string predicates).
    part = ds.partitioning(pa.schema([("chrom", pa.string())]), flavor="hive")
    dataset = ds.dataset(root, format="parquet", partitioning=part)

    filt = None
    if chrom is not None:
        filt = ds.field("chrom") == str(chrom)
    if max_gnomad_af is not None:
        af_filt = ds.field("gnomad_af") <= max_gnomad_af
        filt = af_filt if filt is None else (filt & af_filt)

    table = dataset.to_table(columns=columns, filter=filt)
    return table.to_pylist()


def read_variants_as_objects(case_id: str, base_dir: str | Path | None = None,
                             **kwargs) -> list[Variant]:
    """Read rows back as :class:`Variant` objects (layer metadata restored to raw)."""
    rows = read_variants(case_id, base_dir, **kwargs)
    out: list[Variant] = []
    for r in rows:
        raw: dict[str, Any] = {}
        for k in ("consequence", "impact", "filter", "clinvar", "cadd", "gt", "dp", "gq"):
            if r.get(k) is not None:
                raw[k] = r[k]
        if r.get("gnomad_af") is not None:
            raw["gnomad_af"] = r["gnomad_af"]
        out.append(Variant(
            gene=r.get("gene"), hgvs=r.get("hgvs"),
            chrom=r.get("chrom"), pos=r.get("pos"),
            ref=r.get("ref"), alt=r.get("alt"), rsid=r.get("rsid"),
            allele_freq=r.get("gnomad_af"), raw=raw,
        ))
    return out
