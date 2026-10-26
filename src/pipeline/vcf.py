"""VCF intake + variant parsing.

A lightweight, dependency-free, STREAMING VCF reader. We read line by line and never
load a whole-genome VCF into memory. Inputs for the pilot are small, already-filtered
candidate lists — but the streaming design means a large file won't blow up RAM.

Extracts: chrom, pos, ref, alt, rsid (ID col), and from INFO: gene (ANN/GENE/GENEINFO),
HGVS (ANN/HGVS*), and allele frequency (AF / gnomAD AF fields).
"""
from __future__ import annotations
import gzip
from pathlib import Path
from typing import Iterator

from src.utils.schema import Variant


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


def iter_variants(path: str | Path, max_variants: int = 10000) -> Iterator[Variant]:
    path = Path(path)
    count = 0
    with _open(path) as fh:
        for line in fh:
            if not line or line.startswith("#"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 5:
                continue
            chrom, pos, vid, ref, alt = cols[0], cols[1], cols[2], cols[3], cols[4]
            info = _parse_info(cols[7]) if len(cols) > 7 else {}
            try:
                ipos = int(pos)
            except ValueError:
                continue
            yield Variant(
                gene=_gene_from_info(info),
                hgvs=_hgvs_from_info(info),
                chrom=chrom.replace("chr", ""),
                pos=ipos,
                ref=ref,
                alt=alt.split(",")[0],
                rsid=None if vid in (".", "") else vid,
                allele_freq=_af_from_info(info),
                raw={"info": info} if info else {},
            )
            count += 1
            if count >= max_variants:
                break


def parse_vcf(path: str | Path, max_variants: int = 10000) -> list[Variant]:
    """Parse a (small / already-filtered) VCF into Variant records (streaming internally)."""
    return list(iter_variants(path, max_variants=max_variants))
