"""Stage 01 ingest/normalize tests — fully offline.

Research-use-only tool: these tests exercise the deterministic data layer that
decomposes variants BEFORE any agent sees them. They use tiny inline VCFs and the
bundled demo VCF; no network and no reference FASTA required.
"""
import gzip
from pathlib import Path

import pytest

from src.pipeline import ingest
from src.pipeline.vcf import parse_vcf

CF_VCF = Path("benchmarks/cases/cystic_fibrosis.vcf")

MULTIALLELIC = (
    "##fileformat=VCFv4.2\n"
    "##reference=GRCh38\n"
    '##INFO=<ID=AF,Number=A,Type=Float,Description="Allele Frequency">\n'
    '##INFO=<ID=ANN,Number=.,Type=String,Description="ann">\n'
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    "7\t117559590\trs1\tCTT\tC,CT\t800\tPASS\tAF=0.0001,0.02;ANN=C|inframe|MODERATE|CFTR|c.1A>G\n"
    "12\t102855239\t.\tG\tA\t80\tPASS\tAF=0.00005;ANN=A|missense|MODERATE|PAH|c.728G>A\n"
)

GRCH37_VCF = (
    "##fileformat=VCFv4.2\n"
    "##reference=hg19\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    "1\t11856378\trs1801133\tG\tA\t60\tPASS\tAF=0.3\n"
)


@pytest.fixture(autouse=True)
def _reset_caps():
    """Each test starts from a clean capability cache."""
    ingest._CAPS_CACHE = None
    yield
    ingest._CAPS_CACHE = None


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    if name.endswith(".gz"):
        with gzip.open(p, "wt") as fh:
            fh.write(content)
    else:
        p.write_text(content)
    return p


# --------------------------------------------------------------------------- #
# Header inspection / reference-build detection
# --------------------------------------------------------------------------- #
def test_detect_build_grch38():
    info = ingest.inspect_header(CF_VCF)
    assert info.ok
    assert info.reference_build == "GRCh38"


def test_detect_build_grch37_from_hg19(tmp_path):
    p = _write(tmp_path, "b37.vcf", GRCH37_VCF)
    info = ingest.inspect_header(p)
    assert info.reference_build == "GRCh37"


def test_unknown_build_is_not_fatal(tmp_path):
    p = _write(tmp_path, "nobuild.vcf",
               "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
               "7\t100\t.\tA\tG\t1\tPASS\t.\n")
    info = ingest.inspect_header(p)
    assert info.ok               # usable header
    assert info.reference_build is None
    assert any("unknown" in m for m in info.messages)


# --------------------------------------------------------------------------- #
# Multiallelic split (core of Stage 01) — one Variant per ALT
# --------------------------------------------------------------------------- #
def test_multiallelic_split_bcftools(tmp_path):
    if not ingest.tool_availability().any:
        pytest.skip("no normalization tool installed")
    p = _write(tmp_path, "multi.vcf", MULTIALLELIC)
    variants = parse_vcf(p)
    # 2 input rows, first is bi-allelic (C,CT) -> 3 variants total after split.
    assert len(variants) == 3
    cftr = [v for v in variants if v.gene == "CFTR"]
    assert len(cftr) == 2
    alts = sorted(v.alt for v in cftr)
    assert alts == ["C", "CT"]
    # per-allele AF subset correctly (text preserved, parsed as float)
    af_by_alt = {v.alt: v.allele_freq for v in cftr}
    assert af_by_alt["C"] == 0.0001
    assert af_by_alt["CT"] == 0.02


def test_normalize_to_lines_single_allele_each(tmp_path):
    if not ingest.tool_availability().any:
        pytest.skip("no normalization tool installed")
    p = _write(tmp_path, "multi.vcf", MULTIALLELIC)
    lines = list(ingest.normalize_to_lines(p))
    assert len(lines) == 3
    for ln in lines:
        assert "," not in ln.split("\t")[4]   # ALT column has no comma after split


# --------------------------------------------------------------------------- #
# .vcf.gz streaming
# --------------------------------------------------------------------------- #
def test_gzip_input_streams(tmp_path):
    p = _write(tmp_path, "multi.vcf.gz", MULTIALLELIC)
    variants = parse_vcf(p)
    # with tools -> split to 3; without tools (fallback) -> 2 (first allele only)
    assert len(variants) in (2, 3)
    assert any(v.gene == "PAH" for v in variants)


# --------------------------------------------------------------------------- #
# Graceful fallback when no tool is installed
# --------------------------------------------------------------------------- #
def test_fallback_when_no_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "_CAPS_CACHE", ingest.ToolCaps(bcftools=None, pysam=None))
    p = _write(tmp_path, "multi.vcf", MULTIALLELIC)
    # normalize_to_lines must signal unavailability...
    with pytest.raises(ingest.NormalizationUnavailable):
        list(ingest.normalize_to_lines(p))
    # ...and parse_vcf must still work via the raw line reader (no split).
    variants = parse_vcf(p)
    assert len(variants) == 2   # multiallelic NOT split in fallback; first allele kept
    cftr = [v for v in variants if v.gene == "CFTR"][0]
    assert cftr.alt == "C"      # alt.split(",")[0]


def test_pysam_only_path(tmp_path, monkeypatch):
    caps = ingest.tool_availability()
    if not caps.pysam:
        pytest.skip("pysam not installed")
    # Simulate bcftools missing: pysam path must still split multiallelics.
    monkeypatch.setattr(ingest, "_CAPS_CACHE",
                        ingest.ToolCaps(bcftools=None, pysam=caps.pysam))
    p = _write(tmp_path, "multi.vcf", MULTIALLELIC)
    variants = parse_vcf(p)
    assert len(variants) == 3


# --------------------------------------------------------------------------- #
# Non-breaking: existing small-VCF parsing is unchanged
# --------------------------------------------------------------------------- #
def test_demo_vcf_unchanged_via_normalized_path():
    variants = parse_vcf(CF_VCF)
    assert len(variants) == 2
    cftr = [v for v in variants if v.gene == "CFTR"][0]
    assert cftr.chrom == "7"
    assert cftr.pos == 117559590
    assert cftr.ref == "CTT" and cftr.alt == "C"
    assert cftr.allele_freq == 0.0001
    assert "c.1521_1523delCTT" in (cftr.hgvs or "")


def test_normalized_matches_fallback_for_biallelic(tmp_path, monkeypatch):
    """For a bi-allelic file, the normalized path and the raw fallback agree."""
    normalized = parse_vcf(CF_VCF, normalize=True)
    forced_fallback = parse_vcf(CF_VCF, normalize=False)
    assert len(normalized) == len(forced_fallback) == 2
    for a, b in zip(normalized, forced_fallback):
        assert (a.gene, a.chrom, a.pos, a.ref, a.alt, a.allele_freq) == \
               (b.gene, b.chrom, b.pos, b.ref, b.alt, b.allele_freq)


def test_max_variants_cap_normalized():
    assert len(parse_vcf(CF_VCF, max_variants=1)) == 1
