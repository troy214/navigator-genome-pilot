"""Smoke tests confirming the scaffold wiring imports and runs end-to-end (stubs)."""
from src.utils.schema import CaseInput, Variant, Knowledge
from src.orchestrator.coordinator import Coordinator


def test_schema_builds():
    c = CaseInput(case_id="T1", variants=[Variant(gene="X")])
    assert c.case_id == "T1"
    assert Knowledge.UNKNOWN.value == "unknown"


def test_coordinator_runs_stubs():
    c = CaseInput(case_id="T1", clinical_summary="demo", variants=[Variant(gene="X")])
    out = Coordinator().run(c)
    assert out["case_id"] == "T1"
    assert out["status"] == "scaffold"
    # all 8 agents ran
    assert len(out["agent_results"]) == 8
