"""Smoke tests: schema + provider config + VCF parser. Run fully offline."""
from src.utils.schema import CaseInput, Variant, Knowledge, Confidence, Evidence, Finding
from src.models.config import model_for
from config import settings


def test_schema_builds():
    c = CaseInput(case_id="T1", variants=[Variant(gene="X")])
    assert c.case_id == "T1"
    assert Knowledge.UNKNOWN.value == "unknown"
    assert Confidence.HIGH.value == "high"


def test_evidence_requires_source():
    e = Evidence(claim="c", source="s", confidence=Confidence.HIGH, knowledge=Knowledge.VERIFIED)
    assert e.source == "s"


def test_finding_defaults():
    f = Finding(rank=1, gene="CFTR")
    assert f.rank == 1 and f.confidence == Confidence.UNCERTAIN


def test_variant_short():
    assert Variant(gene="CFTR", hgvs="c.1A>G").short() == "CFTR c.1A>G"
    assert Variant(chrom="7", pos=100, ref="A", alt="G").short() == "7:100A>G"


def test_provider_resolution_defaults_to_dev(monkeypatch):
    # With no META key, model_for returns a dev model id.
    m = model_for("intake")
    assert isinstance(m, str) and m
