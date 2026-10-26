"""VCF parser tests — fully offline, uses the bundled demo VCF."""
from pathlib import Path
from src.pipeline.vcf import parse_vcf, _parse_info, _gene_from_info, _af_from_info

VCF = Path("benchmarks/cases/cystic_fibrosis.vcf")


def test_parse_demo_vcf():
    variants = parse_vcf(VCF)
    assert len(variants) == 2
    cftr = [v for v in variants if v.gene == "CFTR"][0]
    assert cftr.chrom == "7"
    assert cftr.pos == 117559590
    assert cftr.ref == "CTT" and cftr.alt == "C"
    assert cftr.allele_freq == 0.0001
    assert "c.1521_1523delCTT" in (cftr.hgvs or "")


def test_info_helpers():
    info = _parse_info("AF=0.01;GENEINFO=CFTR:1080;ANN=C|inframe|MODERATE|CFTR|c.1A>G")
    assert _gene_from_info(info) == "CFTR"
    assert _af_from_info(info) == 0.01


def test_max_variants_cap():
    assert len(parse_vcf(VCF, max_variants=1)) == 1
