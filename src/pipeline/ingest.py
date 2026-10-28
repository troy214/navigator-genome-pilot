"""Stage 01 of the Navigator genomic streaming data layer: Ingest & Normalize.

RESEARCH USE ONLY — this module is part of a research tool for interpreting
rare-disease genomes. It produces hypotheses for researchers, never a diagnosis
and never medical advice.

What this stage does, BEFORE any agent sees a variant:
  * validate the VCF header and detect the reference build (GRCh37 / GRCh38)
    where it can be derived from ``##reference`` / ``##contig`` — recorded, never
    fatal if unknown;
  * left-align indels and split multiallelic sites / decompose (the core of
    Stage 01). We prefer ``bcftools norm -m-`` (split multiallelics) plus, when a
    reference FASTA is supplied, ``-f <ref>`` for left-alignment. Without a
    reference FASTA we still split multiallelics and simply skip the
    reference-dependent left-align step (logged).
  * stream records — we never load a whole-genome VCF into memory.

Design intent (see docs/DATA_LAYER_DESIGN.md): heavy, deterministic variant
reduction belongs in cheap, auditable data engineering — not in expensive,
non-reproducible LLM reasoning. This module is deliberately NON-LLM.

Fallback discipline (non-breaking): if neither ``bcftools`` nor ``pysam`` is
installed, callers fall back to the original dependency-free line reader in
``src/pipeline/vcf.py``. Normalization is therefore an enhancement, never a hard
requirement.
"""
from __future__ import annotations

import gzip
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

log = logging.getLogger("navigator.ingest")

# Standard contigs we inject into header-light demo/snippet VCFs so that a strict
# ``bcftools`` run does not reject records whose contig is not declared in the
# header. Injecting unused contigs is harmless; bcftools ignores them.
_STD_CHROMS = [str(i) for i in range(1, 23)] + ["X", "Y", "MT", "M"]
_STD_CONTIGS = _STD_CHROMS + [f"chr{c}" for c in _STD_CHROMS]


# --------------------------------------------------------------------------- #
# Capability detection
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ToolCaps:
    bcftools: str | None = None   # version string if available, else None
    pysam: str | None = None      # version string if available, else None

    @property
    def any(self) -> bool:
        return bool(self.bcftools or self.pysam)


def _bcftools_version() -> str | None:
    exe = shutil.which("bcftools")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
        first = (out.stdout or "").splitlines()[0] if out.stdout else "bcftools"
        return first.replace("bcftools", "").strip() or "unknown"
    except Exception:
        return None


def _pysam_version() -> str | None:
    try:
        import pysam  # noqa: F401
        return getattr(pysam, "__version__", "unknown")
    except Exception:
        return None


_CAPS_CACHE: ToolCaps | None = None


def tool_availability(refresh: bool = False) -> ToolCaps:
    """Return which normalization tools are installed (cached)."""
    global _CAPS_CACHE
    if _CAPS_CACHE is None or refresh:
        _CAPS_CACHE = ToolCaps(bcftools=_bcftools_version(), pysam=_pysam_version())
    return _CAPS_CACHE


# --------------------------------------------------------------------------- #
# Header inspection: validation + reference-build detection
# --------------------------------------------------------------------------- #
def _open_text(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt")
    return open(path, "rt")


def read_header(path: str | Path) -> list[str]:
    """Stream only the ``##``/``#CHROM`` header lines (never the whole file)."""
    path = Path(path)
    header: list[str] = []
    with _open_text(path) as fh:
        for line in fh:
            if line.startswith("#"):
                header.append(line.rstrip("\n"))
                if line.startswith("#CHROM"):
                    break
            else:
                break
    return header


@dataclass
class HeaderInfo:
    ok: bool
    reference_build: str | None      # "GRCh37" | "GRCh38" | None (unknown)
    messages: list[str]
    contig_ids: list[str]


def _normalize_build_token(tok: str) -> str | None:
    t = tok.lower()
    if "grch38" in t or "hg38" in t or t.endswith("38"):
        return "GRCh38"
    if "grch37" in t or "hg19" in t or t.endswith("37") or "hg37" in t:
        return "GRCh37"
    return None


def inspect_header(path: str | Path) -> HeaderInfo:
    """Validate the VCF header and derive the reference build where possible.

    Never raises for a merely unknown build — Stage 01 records what it can and
    carries on (the research tool must be able to say when it does not know).
    """
    header = read_header(path)
    messages: list[str] = []
    contig_ids: list[str] = []
    build: str | None = None

    has_fileformat = any(h.startswith("##fileformat") for h in header)
    has_chrom = any(h.startswith("#CHROM") for h in header)
    if not has_fileformat:
        messages.append("missing ##fileformat line")
    if not has_chrom:
        messages.append("missing #CHROM column header")

    for h in header:
        if h.startswith("##reference"):
            val = h.split("=", 1)[1] if "=" in h else ""
            b = _normalize_build_token(val)
            if b:
                build = build or b
        if h.startswith("##contig"):
            # ##contig=<ID=7,length=...,assembly=GRCh38>
            inner = h[h.find("<") + 1:h.rfind(">")] if "<" in h else ""
            cid = None
            for part in inner.split(","):
                if part.strip().startswith("ID="):
                    cid = part.split("=", 1)[1].strip()
                if part.strip().lower().startswith("assembly=") and not build:
                    build = _normalize_build_token(part.split("=", 1)[1]) or build
            if cid:
                contig_ids.append(cid)

    if build:
        messages.append(f"reference build detected: {build}")
    else:
        messages.append("reference build unknown (not declared in header)")

    ok = has_chrom  # a usable VCF minimally needs the column header
    return HeaderInfo(ok=ok, reference_build=build, messages=messages, contig_ids=contig_ids)


# --------------------------------------------------------------------------- #
# Normalization: bcftools (preferred) -> pysam -> (caller falls back)
# --------------------------------------------------------------------------- #
class NormalizationUnavailable(RuntimeError):
    """Raised when no normalization tool can process the input."""


def _write_tmp_with_contigs(path: Path, present: list[str]) -> Path:
    """Stream-copy ``path`` into a temp VCF, injecting any missing standard
    ``##contig`` lines so strict bcftools does not reject header-light inputs.

    Constant memory: the body is copied line by line, never buffered whole.
    """
    missing = [c for c in _STD_CONTIGS if c not in present]
    inject = [f"##contig=<ID={c}>" for c in missing]

    fd, tmp_name = tempfile.mkstemp(suffix=".vcf", prefix="navigator_norm_")
    os.close(fd)
    tmp = Path(tmp_name)
    with _open_text(path) as src, open(tmp, "wt") as dst:
        injected = False
        for line in src:
            if line.startswith("#CHROM") and not injected:
                for c in inject:
                    dst.write(c + "\n")
                injected = True
                dst.write(line)
            elif not line.startswith("#") and not injected:
                # no #CHROM line seen (malformed) — inject before first record
                for c in inject:
                    dst.write(c + "\n")
                injected = True
                dst.write(line)
            else:
                dst.write(line)
    return tmp


def _bcftools_norm_lines(path: Path, ref_fasta: str | None) -> Iterator[str]:
    """Yield normalized VCF *data* lines from ``bcftools norm -m-`` (streaming).

    Adds ``-f <ref_fasta>`` for left-alignment when a reference FASTA is given;
    otherwise left-align is skipped (split-multiallelics only) and this is logged.
    """
    exe = shutil.which("bcftools")
    assert exe  # guarded by caller

    info = inspect_header(path)
    tmp = _write_tmp_with_contigs(path, info.contig_ids)
    cmd = [exe, "norm", "-m-", "-Ov"]
    if ref_fasta and Path(ref_fasta).exists():
        cmd += ["-f", ref_fasta]
        log.info("bcftools norm: left-aligning against reference FASTA %s", ref_fasta)
    else:
        if ref_fasta:
            log.warning("reference FASTA %s not found; left-align skipped", ref_fasta)
        else:
            log.info("no reference FASTA; splitting multiallelics only (left-align skipped)")
    cmd.append(str(tmp))

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.startswith("#"):
                continue
            yield line.rstrip("\n")
        proc.wait(timeout=600)
        if proc.returncode not in (0, None):
            err = (proc.stderr.read() if proc.stderr else "")[:300]
            raise NormalizationUnavailable(f"bcftools norm failed (rc={proc.returncode}): {err}")
    finally:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _split_info_by_allele(info: str, alt_index: int, n_alts: int) -> str:
    """Subset Number=A-style INFO fields (e.g. AF) to one allele, preserving the
    original TEXT (so float precision is never altered). Fields whose value count
    does not match the allele count are copied verbatim.
    """
    if info in (".", ""):
        return info
    out_fields: list[str] = []
    for field in info.split(";"):
        if "=" in field:
            k, v = field.split("=", 1)
            parts = v.split(",")
            if len(parts) == n_alts and n_alts > 1:
                out_fields.append(f"{k}={parts[alt_index]}")
            else:
                out_fields.append(field)
        else:
            out_fields.append(field)
    return ";".join(out_fields)


def _pysam_norm_lines(path: Path) -> Iterator[str]:
    """Yield normalized VCF data lines using pysam for robust streaming.

    pysam handles bgzipped input and header validation; we split multiallelic
    records at the TEXT level (re-using the original record text) so values are
    preserved exactly. Reference-dependent left-align is skipped (logged).
    """
    import pysam

    log.info("normalizing with pysam (left-align skipped; split multiallelics only)")
    vf = pysam.VariantFile(str(path))
    try:
        for rec in vf:
            cols = str(rec).rstrip("\n").split("\t")
            if len(cols) < 5:
                continue
            alts = cols[4].split(",")
            if len(alts) <= 1:
                yield "\t".join(cols)
                continue
            n = len(alts)
            info = cols[7] if len(cols) > 7 else ""
            for i, alt in enumerate(alts):
                new_cols = list(cols)
                new_cols[4] = alt
                if len(new_cols) > 7:
                    new_cols[7] = _split_info_by_allele(info, i, n)
                yield "\t".join(new_cols)
    finally:
        vf.close()


def normalize_to_lines(path: str | Path, ref_fasta: str | None = None) -> Iterator[str]:
    """Stream normalized VCF data lines using the best available tool.

    Order: bcftools (split + optional left-align) -> pysam (split only) ->
    raise ``NormalizationUnavailable`` (caller then uses the line-reader fallback).
    """
    path = Path(path)
    caps = tool_availability()
    if caps.bcftools:
        yield from _bcftools_norm_lines(path, ref_fasta)
        return
    if caps.pysam:
        yield from _pysam_norm_lines(path)
        return
    raise NormalizationUnavailable("neither bcftools nor pysam is installed")
