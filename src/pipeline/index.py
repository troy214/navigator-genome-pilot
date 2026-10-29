"""Stage 04 of the Navigator genomic streaming data layer: Index.

RESEARCH USE ONLY — part of a research tool for interpreting rare-disease genomes.
Outputs are hypotheses for researchers, never a diagnosis and never medical advice.

Two deterministic, non-LLM indexes over the normalized + QC'd variants:

  1. **bgzip + tabix** on the normalized VCF, for O(log n) genomic *region* queries
     (``chrom:start-end``) — built with pysam's bundled htslib (no external binaries
     required). Enables "what variants fall in this gene's locus?" without a full scan.
  2. **Lightweight lookup maps** ``gene -> [row indices]`` and ``rsID -> row index``,
     for O(1) agent lookups by symbol / dbSNP id. Held in memory and persisted as JSON.

Non-breaking / optional: if ``pysam`` is unavailable the tabix index is skipped
(:class:`IndexUnavailable`); the JSON lookup maps are pure-Python and always work.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from src.utils.schema import Variant

log = logging.getLogger("navigator.index")


class IndexUnavailable(RuntimeError):
    """Raised when pysam/htslib is not available for tabix indexing."""


def _pysam():
    try:
        import pysam
        return pysam
    except Exception as e:  # pragma: no cover - environment dependent
        raise IndexUnavailable(f"pysam not available: {e}")


# --------------------------------------------------------------------------- #
# bgzip + tabix
# --------------------------------------------------------------------------- #
_MINIMAL_CONTIGS = [str(i) for i in range(1, 23)] + ["X", "Y", "MT", "M"]


def write_sorted_vcf(data_lines: Iterable[str], out_path: str | Path,
                     header_lines: list[str] | None = None) -> Path:
    """Write a minimal, coordinate-sorted VCF (header + sorted body).

    tabix requires records sorted by (chrom, pos). We sort in memory here; for the
    candidate-set sizes this layer targets (tens–thousands) that is trivial.
    """
    out_path = Path(out_path)
    rows = []
    for line in data_lines:
        if not line or line.startswith("#"):
            continue
        cols = line.rstrip("\n").split("\t")
        if len(cols) < 2:
            continue
        try:
            key = (cols[0], int(cols[1]))
        except ValueError:
            continue
        rows.append((key, line.rstrip("\n")))
    # sort by chrom (natural-ish) then pos
    def _chrom_key(c: str):
        c = c[3:] if c.lower().startswith("chr") else c
        return (0, int(c)) if c.isdigit() else (1, c)
    rows.sort(key=lambda r: (_chrom_key(r[0][0]), r[0][1]))

    header = header_lines or (
        ["##fileformat=VCFv4.2"]
        + [f"##contig=<ID={c}>" for c in _MINIMAL_CONTIGS]
        + ["#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO"]
    )
    with open(out_path, "wt") as fh:
        for h in header:
            fh.write(h + "\n")
        for _, line in rows:
            fh.write(line + "\n")
    return out_path


def bgzip_and_tabix(vcf_path: str | Path) -> Path:
    """bgzip-compress a sorted VCF and build its .tbi tabix index.

    Returns the path to the ``.vcf.gz``. Uses pysam's bundled htslib, so it works
    even when standalone ``bgzip``/``tabix`` binaries are not on PATH.
    """
    pysam = _pysam()
    vcf_path = Path(vcf_path)
    gz_path = Path(str(vcf_path) + ".gz")
    # tabix_compress -> bgzip; tabix_index with the vcf preset builds the .tbi
    pysam.tabix_compress(str(vcf_path), str(gz_path), force=True)
    pysam.tabix_index(str(gz_path), preset="vcf", force=True)
    log.info("built tabix index for %s", gz_path.name)
    return gz_path


def region_query(gz_path: str | Path, chrom: str,
                 start: int | None = None, end: int | None = None) -> list[str]:
    """Return VCF data lines overlapping ``chrom[:start-end]`` (1-based inclusive).

    Tolerates ``chr`` prefix mismatch by trying both forms.
    """
    pysam = _pysam()
    tbx = pysam.TabixFile(str(gz_path))
    try:
        candidates = [chrom]
        if chrom.lower().startswith("chr"):
            candidates.append(chrom[3:])
        else:
            candidates.append("chr" + chrom)
        for c in candidates:
            if c not in tbx.contigs:
                continue
            # pysam.fetch is 0-based half-open; convert from 1-based inclusive
            s = (start - 1) if start else None
            e = end if end else None
            return list(tbx.fetch(c, s, e))
        return []
    finally:
        tbx.close()


# --------------------------------------------------------------------------- #
# Lightweight gene / rsID lookup maps
# --------------------------------------------------------------------------- #
def build_lookup_maps(variants: Iterable[Variant]) -> dict:
    """Build ``gene -> [indices]`` and ``rsid -> index`` maps over a variant list.

    Indices refer to the position of the variant in the given ordered list, so the
    maps can be used alongside the same ordered candidate set (or the Parquet rows).
    """
    gene_map: dict[str, list[int]] = {}
    rsid_map: dict[str, int] = {}
    n = 0
    for i, v in enumerate(variants):
        n = i + 1
        if v.gene:
            gene_map.setdefault(v.gene, []).append(i)
        if v.rsid:
            rsid_map[v.rsid] = i
    return {"n": n, "gene": gene_map, "rsid": rsid_map}


def save_lookup_maps(maps: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(maps, indent=0, sort_keys=True))
    return path


def load_lookup_maps(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def lookup_by_gene(maps: dict, gene: str) -> list[int]:
    return maps.get("gene", {}).get(gene, [])


def lookup_by_rsid(maps: dict, rsid: str) -> int | None:
    return maps.get("rsid", {}).get(rsid)
