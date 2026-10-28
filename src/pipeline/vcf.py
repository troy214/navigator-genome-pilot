"""VCF intake + variant parsing.

RESEARCH USE ONLY — part of a research tool for interpreting rare-disease genomes.
Outputs are hypotheses for researchers, never a diagnosis and never medical advice.

Two layers, same public interface (``parse_vcf`` / ``iter_variants``):

  1. **Normalized path (Stage 01)** — when ``bcftools`` and/or ``pysam`` are
     installed, records are streamed through ``src.pipeline.ingest`` first:
     multiallelic sites are split / decomposed and (with a reference FASTA) indels
     are left-aligned, BEFORE they become ``Variant`` records. See
     docs/DATA_LAYER_DESIGN.md.
  2. **Fallback path** — the original lightweight, dependency-free, line-by-line
     reader. Used for tiny inputs or whenever no normalization tool is installed,
     so parsing never hard-depends on external binaries.

Both paths read line by line and never load a whole-genome VCF into memory.

Extracts: chrom, pos, ref, alt, rsid (ID col), and from INFO: gene (ANN/GENE/GENEINFO),
HGVS (ANN/HGVS*), and allele frequency (AF / gnomAD AF fields).
"""
from __future__ import annotations
import gzip
import logging
from pathlib import Path
from typing import Iterator

from src.utils.schema import Variant

log = logging.getLogger("navigator.vcf")


def _open(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt")
    return open(path, "rt")


def _parse_info(info: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if info in (".", ""):
        return out
    for field in info.split(";"):
        if "=" in field:
            k, v = field.split("=", 1)
            out[k] = v
        else:
            out[field] = "true"
    return out


def _gene_from_info(info: dict[str, str]) -> str | None:
    # snpEff/VEP style ANN=allele|effect|impact|GENE|...
    ann = info.get("ANN") or info.get("CSQ")
    if ann:
        first = ann.split(",")[0].split("|")
        if len(first) > 3 and first[3]:
            return first[3]
    for k in ("GENE", "GENEINFO", "GeneName", "gene"):
        if info.get(k):
            # GENEINFO can look like "CFTR:1080"
            return info[k].split(":")[0].split("|")[0]
    return None


def _hgvs_from_info(info: dict[str, str]) -> str | None:
    ann = info.get("ANN") or info.get("CSQ")
    if ann:
        for part in ann.split(",")[0].split("|"):
            if part.startswith(("c.", "p.", "NM_", "NC_", "ENST")):
                return part
    for k in ("HGVS", "HGVSc", "HGVS_C", "CLNHGVS"):
        if info.get(k):
            return info[k].split(",")[0]
    return None


def _af_from_info(info: dict[str, str]) -> float | None:
    for k in ("AF", "gnomad_AF", "AF_popmax", "gnomAD_AF", "MAF"):
        v = info.get(k)
        if v:
            try:
                return float(v.split(",")[0])
            except ValueError:
                continue
    return None


def _variant_from_cols(cols: list[str]) -> Variant | None:
    """Build a Variant from one VCF data row (list of tab-separated columns).

    Shared by both the normalized and the fallback path so a given record yields
    an identical Variant regardless of which engine produced the line.
    """
    if len(cols) < 5:
        return None
    chrom, pos, vid, ref, alt = cols[0], cols[1], cols[2], cols[3], cols[4]
    info = _parse_info(cols[7]) if len(cols) > 7 else {}
    try:
        ipos = int(pos)
    except ValueError:
        return None
    return Variant(
        gene=_gene_from_info(info),
        hgvs=_hgvs_from_info(info),
        chrom=chrom.replace("chr", ""),
        pos=ipos,
        ref=ref,
        alt=alt.split(",")[0],   # normalized lines are already single-allele; fallback keeps first
        rsid=None if vid in (".", "") else vid,
        allele_freq=_af_from_info(info),
        raw={"info": info} if info else {},
    )


def _iter_variants_raw(path: Path, max_variants: int) -> Iterator[Variant]:
    """Original dependency-free fallback: stream the VCF line by line."""
    count = 0
    with _open(path) as fh:
        for line in fh:
            if not line or line.startswith("#"):
                continue
            v = _variant_from_cols(line.rstrip("\n").split("\t"))
            if v is None:
                continue
            yield v
            count += 1
            if count >= max_variants:
                break


def _iter_variants_normalized(path: Path, max_variants: int,
                              ref_fasta: str | None) -> Iterator[Variant]:
    """Stage 01 path: stream bcftools/pysam-normalized lines into Variants.

    Raises ingest.NormalizationUnavailable if no tool can process the input, so
    the caller can fall back to the raw reader.
    """
    from src.pipeline import ingest  # local import keeps ingest optional
    count = 0
    for line in ingest.normalize_to_lines(path, ref_fasta=ref_fasta):
        v = _variant_from_cols(line.split("\t"))
        if v is None:
            continue
        yield v
        count += 1
        if count >= max_variants:
            break


def iter_variants(path: str | Path, max_variants: int = 10000, *,
                  normalize: bool = True, ref_fasta: str | None = None) -> Iterator[Variant]:
    """Stream Variant records from a VCF.

    When ``normalize`` is True and a normalization tool is installed, records are
    decomposed/split (and left-aligned if ``ref_fasta`` is given) via Stage 01
    before parsing. On any normalization failure — or when no tool is installed —
    this transparently falls back to the original line-by-line reader, so callers
    (e.g. the Intake agent) need no changes.
    """
    path = Path(path)
    if normalize:
        try:
            from src.pipeline import ingest
            if ingest.tool_availability().any:
                yielded = False
                try:
                    for v in _iter_variants_normalized(path, max_variants, ref_fasta):
                        yielded = True
                        yield v
                    return
                except ingest.NormalizationUnavailable as e:
                    log.info("normalization unavailable (%s); using line-reader fallback", e)
                except Exception as e:  # defensive: never let Stage 01 break intake
                    if yielded:
                        # partial output already emitted — re-raising would duplicate;
                        # surface the error instead of silently truncating.
                        raise
                    log.warning("normalization failed (%s); using line-reader fallback", e)
        except Exception as e:
            log.warning("ingest layer unavailable (%s); using line-reader fallback", e)
    yield from _iter_variants_raw(path, max_variants)


def parse_vcf(path: str | Path, max_variants: int = 10000, *,
              normalize: bool = True, ref_fasta: str | None = None) -> list[Variant]:
    """Parse a VCF into Variant records (streaming internally).

    Uses Stage 01 normalization when available (split multiallelics / left-align),
    otherwise the dependency-free fallback reader. Non-breaking: the signature is
    a superset of the original, so existing calls (``parse_vcf(path)``) are unchanged.
    """
    return list(iter_variants(path, max_variants=max_variants,
                              normalize=normalize, ref_fasta=ref_fasta))
