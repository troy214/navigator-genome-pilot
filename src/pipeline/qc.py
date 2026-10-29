"""Stage 02 of the Navigator genomic streaming data layer: QC & Hard Filters.

RESEARCH USE ONLY — part of a research tool for interpreting rare-disease genomes.
Outputs are hypotheses for researchers, never a diagnosis and never medical advice.

What this stage does, BEFORE any agent sees a variant (and AFTER Stage 01 has
normalized / split records): a deterministic, non-LLM streaming filter that removes
low-quality or masked calls so only trustworthy variants continue down the layer.

Filters applied (each independently configurable, see ``QCThresholds``):
  * ``FILTER`` column must be ``PASS`` (``.`` — "no filtering applied" — is treated as
    acceptable so header-light demo VCFs are not dropped);
  * depth ``DP`` ≥ ``min_dp``;
  * genotype quality ``GQ`` ≥ ``min_gq``;
  * allele balance ``AB`` (from ``AD``) within ``[min_ab, max_ab]`` for heterozygous calls;
  * optional BED region mask to exclude low-complexity / known-artifact regions.

MISSING-FIELD POLICY (important and deliberate):
  Demo / snippet VCFs frequently carry no ``FORMAT``/sample columns, so ``DP``, ``GQ``
  and ``AD`` are simply absent. A variant whose field is ABSENT **passes** the
  corresponding check rather than being dropped — we never discard a variant for a
  quality metric we cannot see (the "say when it doesn't know" discipline). Only a
  field that is PRESENT and fails its threshold causes a drop. This keeps the current
  demo cases unchanged while still enforcing QC on real, fully-populated VCFs.

Streaming: operates line by line over Stage 01's normalized VCF data lines; never
loads the whole file into memory.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

log = logging.getLogger("navigator.qc")


# --------------------------------------------------------------------------- #
# Configurable thresholds
# --------------------------------------------------------------------------- #
@dataclass
class QCThresholds:
    """Hard-filter thresholds. ``None`` disables an individual check.

    Defaults are intentionally permissive (only ``require_pass`` is on) so the
    existing demo cases — which are already PASS and carry no FORMAT fields — are
    unchanged. Use :meth:`recommended` for realistic WES/WGS thresholds.
    """
    require_pass: bool = True
    min_dp: int | None = None          # minimum read depth
    min_gq: int | None = None          # minimum genotype quality
    min_ab: float | None = None        # min allele balance for hets (e.g. 0.2)
    max_ab: float | None = None        # max allele balance for hets (e.g. 0.8)

    @classmethod
    def recommended(cls) -> "QCThresholds":
        """A sensible germline preset (applied only where fields exist)."""
        return cls(require_pass=True, min_dp=10, min_gq=20, min_ab=0.2, max_ab=0.8)


@dataclass
class QCStats:
    """Provenance for the QC stage: counts and per-reason drops."""
    total: int = 0
    kept: int = 0
    dropped: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def _drop(self, reason: str) -> None:
        self.dropped += 1
        self.reasons[reason] = self.reasons.get(reason, 0) + 1

    def summary(self) -> str:
        parts = [f"{k}={v}" for k, v in sorted(self.reasons.items())]
        return (f"QC kept {self.kept}/{self.total}"
                + (f"; dropped: {', '.join(parts)}" if parts else "; dropped: 0"))


# --------------------------------------------------------------------------- #
# BED region mask (optional)
# --------------------------------------------------------------------------- #
class BedMask:
    """A minimal BED interval set for excluding masked regions.

    BED is 0-based, half-open [start, end). VCF POS is 1-based. A variant at VCF
    POS p (1-based) falls in a BED interval [s, e) iff ``s <= p-1 < e``.
    Intervals are stored per-chromosome and matched by linear scan — fine for the
    small artifact/low-complexity BEDs used here. Returns False for any chrom not
    in the BED (nothing masked there).
    """

    def __init__(self, intervals: dict[str, list[tuple[int, int]]] | None = None):
        self._by_chrom: dict[str, list[tuple[int, int]]] = intervals or {}

    @staticmethod
    def _norm_chrom(c: str) -> str:
        return c[3:] if c.lower().startswith("chr") else c

    @classmethod
    def from_file(cls, bed_path: str | Path) -> "BedMask":
        by_chrom: dict[str, list[tuple[int, int]]] = {}
        p = Path(bed_path)
        with open(p, "rt") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith(("#", "track", "browser")):
                    continue
                parts = line.split("\t") if "\t" in line else line.split()
                if len(parts) < 3:
                    continue
                chrom = cls._norm_chrom(parts[0])
                try:
                    start, end = int(parts[1]), int(parts[2])
                except ValueError:
                    continue
                by_chrom.setdefault(chrom, []).append((start, end))
        return cls(by_chrom)

    def contains(self, chrom: str, pos_1based: int) -> bool:
        ivs = self._by_chrom.get(self._norm_chrom(chrom))
        if not ivs:
            return False
        p0 = pos_1based - 1
        return any(s <= p0 < e for s, e in ivs)


# --------------------------------------------------------------------------- #
# FORMAT/sample parsing (DP / GQ / AD / GT)
# --------------------------------------------------------------------------- #
def _info_dict(info: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if info in (".", ""):
        return out
    for fld in info.split(";"):
        if "=" in fld:
            k, v = fld.split("=", 1)
            out[k] = v
        else:
            out[fld] = "true"
    return out


def parse_sample_fields(cols: list[str]) -> dict[str, str]:
    """Extract DP/GQ/AD/GT from FORMAT (col 8) + first sample (col 9).

    Falls back to INFO for DP when there is no sample column. Returns only the
    fields actually present; absent fields are simply not in the dict.
    """
    out: dict[str, str] = {}
    # FORMAT + first sample
    if len(cols) >= 10 and cols[8] not in (".", ""):
        keys = cols[8].split(":")
        vals = cols[9].split(":")
        for k, v in zip(keys, vals):
            if v not in (".", ""):
                out[k] = v
    # DP can also live in INFO
    if "DP" not in out and len(cols) > 7:
        info = _info_dict(cols[7])
        if "DP" in info:
            out["DP"] = info["DP"]
    return out


def _allele_balance(sample: dict[str, str]) -> float | None:
    """AB = alt_depth / total_depth from the AD field, else None."""
    ad = sample.get("AD")
    if not ad:
        return None
    try:
        depths = [int(x) for x in ad.split(",") if x not in (".", "")]
    except ValueError:
        return None
    total = sum(depths)
    if total <= 0 or len(depths) < 2:
        return None
    return depths[1] / total  # first ALT allele balance


def _is_het(sample: dict[str, str]) -> bool:
    gt = sample.get("GT", "")
    alleles = gt.replace("|", "/").split("/")
    uniq = {a for a in alleles if a not in (".", "")}
    return len(uniq) > 1


# --------------------------------------------------------------------------- #
# The streaming QC filter
# --------------------------------------------------------------------------- #
def passes(cols: list[str], thresholds: QCThresholds,
           bed: BedMask | None = None) -> tuple[bool, str | None]:
    """Return (kept, drop_reason). A field that is ABSENT never causes a drop."""
    if len(cols) < 7:
        return False, "malformed"

    # FILTER == PASS (treat '.' as acceptable — no filtering applied)
    if thresholds.require_pass:
        filt = cols[6]
        if filt not in ("PASS", ".", ""):
            return False, "filter_not_pass"

    # BED region mask
    if bed is not None:
        try:
            if bed.contains(cols[0], int(cols[1])):
                return False, "bed_masked"
        except ValueError:
            pass

    sample = parse_sample_fields(cols)

    if thresholds.min_dp is not None and "DP" in sample:
        try:
            if int(sample["DP"]) < thresholds.min_dp:
                return False, "low_dp"
        except ValueError:
            pass

    if thresholds.min_gq is not None and "GQ" in sample:
        try:
            if float(sample["GQ"]) < thresholds.min_gq:
                return False, "low_gq"
        except ValueError:
            pass

    if (thresholds.min_ab is not None or thresholds.max_ab is not None) and _is_het(sample):
        ab = _allele_balance(sample)
        if ab is not None:
            if thresholds.min_ab is not None and ab < thresholds.min_ab:
                return False, "low_ab"
            if thresholds.max_ab is not None and ab > thresholds.max_ab:
                return False, "high_ab"

    return True, None


def qc_filter_lines(lines: Iterable[str], thresholds: QCThresholds | None = None,
                    bed: BedMask | None = None,
                    stats: QCStats | None = None) -> Iterator[str]:
    """Stream VCF data lines, yielding only those that pass QC.

    ``thresholds`` defaults to the permissive :class:`QCThresholds` (PASS-only), so
    demo inputs are unaffected. ``stats`` (if provided) accumulates provenance.
    """
    thresholds = thresholds or QCThresholds()
    for line in lines:
        if not line or line.startswith("#"):
            continue
        cols = line.rstrip("\n").split("\t")
        if stats is not None:
            stats.total += 1
        ok, reason = passes(cols, thresholds, bed)
        if ok:
            if stats is not None:
                stats.kept += 1
            yield line
        elif stats is not None:
            stats._drop(reason or "unknown")


def qc_filter_file(vcf_path: str | Path, thresholds: QCThresholds | None = None,
                   bed_path: str | Path | None = None) -> tuple[list[str], QCStats]:
    """Convenience: read a (normalized) VCF file and return (kept_lines, stats).

    Reads only data lines. For the streaming layer use :func:`qc_filter_lines`
    directly on Stage 01's ``normalize_to_lines`` output.
    """
    from src.pipeline.ingest import _open_text  # reuse gzip-aware opener
    bed = BedMask.from_file(bed_path) if bed_path else None
    stats = QCStats()

    def _data_lines() -> Iterator[str]:
        with _open_text(Path(vcf_path)) as fh:
            for line in fh:
                if line and not line.startswith("#"):
                    yield line.rstrip("\n")

    kept = list(qc_filter_lines(_data_lines(), thresholds, bed, stats))
    log.info(stats.summary())
    return kept, stats
