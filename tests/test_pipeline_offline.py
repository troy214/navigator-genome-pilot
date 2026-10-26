"""End-to-end coordinator test with LLM + network mocked out (fully offline).

Verifies the pipeline runs all 8 agents, degrades gracefully when external sources are
unavailable, still produces a dossier PDF, and keeps the red-team context isolated.
"""
import json
from pathlib import Path

import pytest

from src.utils.schema import CaseInput, Variant


@pytest.fixture(autouse=True)
def mock_externals(monkeypatch):
    # Mock the model client: one canned JSON serves every agent's expected keys.
    def fake_json(self, system, user, temperature=0.2, default=None):
        return {"phenotypes": ["anemia"], "claims": [], "critiques":
                [{"issue": "limited evidence", "severity": "moderate"}],
                "rationale": "test rationale"}

    def fake_text(self, system, user, temperature=0.2):
        return "test"

    monkeypatch.setattr("src.models.meta_client.MetaModelClient.complete_json", fake_json)
    monkeypatch.setattr("src.models.meta_client.MetaModelClient.complete", fake_text)

    # Mock all external HTTP: everything "unavailable" -> exercises graceful degradation.
    monkeypatch.setattr("src.utils.http.get_json", lambda *a, **k: None)
    monkeypatch.setattr("src.utils.http.post_json", lambda *a, **k: None)
    # HPO falls back to bundled subset for 'anemia'.


def test_full_pipeline_offline(tmp_path):
    from src.orchestrator.coordinator import Coordinator
    case = CaseInput(
        case_id="TEST-OFFLINE",
        clinical_summary="child with anemia",
        variants=[Variant(gene="HBB", hgvs="c.20A>T", chrom="11", pos=5227002,
                          ref="T", alt="A", allele_freq=0.001)])
    out = Coordinator().run(case, persist=False)

    assert out["status"] == "complete"
    assert len(out["agent_results"]) == 8
    # dossier produced even though all external sources were down
    assert out["dossier"]["findings"], "should still rank the provided gene"
    assert out["dossier"]["findings"][0]["gene"] == "HBB"
    # PDF was rendered
    assert out["pdf_path"].endswith(".pdf")
    assert Path(out["pdf_path"]).exists()


def test_red_team_isolation(monkeypatch):
    """Red team must receive only raw evidence, never a leading hypothesis/conclusion."""
    from src.agents.red_team import RedTeamAgent
    captured = {}

    def capture_json(self, system, user, temperature=0.2, default=None):
        captured["user"] = user
        return {"critiques": []}

    monkeypatch.setattr("src.models.meta_client.MetaModelClient.complete_json", capture_json)
    agent = RedTeamAgent()
    agent.run(CaseInput(case_id="X"), {"evidence": [
        {"claim": "CFTR pathogenic", "source": "ClinVar", "confidence": "high",
         "knowledge": "verified", "agent": "database"}]})
    # the prompt should contain evidence but no field named 'conclusion'/'hypothesis'
    assert "conclusion" not in captured["user"].lower()
    assert "leading hypothesis" not in captured["user"].lower()


def test_absent_vs_benign_distinction():
    """Database agent must label an absent ClinVar record as unknown, not benign."""
    from src.clients import clinvar
    # With http mocked to None, availability is False (not a benign claim).
    res = clinvar.query("FAKEGENE")
    assert res["available"] is False
