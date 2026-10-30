"""Offline tests for the FACILITY data-layer gate + per-request variant cap ordering.

These prove the ordering fix on the authenticated /api/v1/analyze path:

  * With the facility gate ON, a VCF whose RAW record count exceeds the cap is NOT
    rejected with 413 when the reduced (post-data-layer) candidate set is within the cap.
    The agents then consume the reduced variants and vcf_path is cleared (no double gate).
  * With the facility gate OFF, the raw-record cap still returns 413 (unchanged behavior).
  * With the gate ON but the reduced set STILL over the cap, the 413 "variant_cap_exceeded"
    shape is preserved (submitted_variants = reduced count).
  * If the reduction raises, the path fails safe to the raw-record cap.

No live LLM / network calls: Coordinator.run is mocked and the data-layer reduction
(``src.pipeline.data_layer.run``) is stubbed so the candidate count is deterministic.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from config import settings
from src.pipeline import data_layer
from src.utils import api_keys
from src.utils.schema import Variant
from src.utils.throttle import throttler


@pytest.fixture(autouse=True)
def _tmp_store_and_reset(tmp_path, monkeypatch):
    """Throwaway key store, auth ON, small deterministic cap, fresh throttler."""
    store = tmp_path / "api_keys.json"
    monkeypatch.setattr(settings, "API_KEYS_STORE", str(store))
    monkeypatch.setattr(settings, "API_KEYS_REQUIRED", True)
    monkeypatch.setattr(settings, "API_MAX_VARIANTS_PER_REQUEST", 50)
    monkeypatch.setattr(settings, "API_REQUESTS_PER_MINUTE", 1000)
    monkeypatch.setattr(settings, "API_REQUESTS_PER_DAY", 1000)
    monkeypatch.setattr(settings, "API_MAX_CONCURRENT_ANALYSES", 100)
    throttler.reset()
    yield store
    throttler.reset()


@pytest.fixture
def client(monkeypatch):
    """TestClient whose Coordinator.run is mocked AND records the case it receives.

    Capturing the case lets us assert the facility path handed the pipeline the REDUCED
    variants with vcf_path cleared (so the coordinator's own gate never runs again).
    """
    from app.backend import main

    captured: dict = {}

    def _fake_run(self, case):
        captured["case"] = case
        return {
            "case_id": case.case_id,
            "status": "ok",
            "provider": "dev",
            "dossier": {"findings": []},
            "agent_results": [],
        }

    monkeypatch.setattr(main.Coordinator, "run", _fake_run)
    c = TestClient(main.app)
    c.captured = captured  # type: ignore[attr-defined]
    return c


def _big_vcf(n_records: int) -> bytes:
    """A VCF with n_records data lines (plus a 2-line header)."""
    data = "".join(f"7\t{1000 + i}\t.\tA\tG\n" for i in range(n_records))
    return ("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\n" + data).encode()


def _stub_reduction(monkeypatch, n_candidates: int):
    """Stub data_layer.run so reduction deterministically yields n_candidates variants."""
    def _fake_data_layer_run(case, config=None):
        variants = [Variant(gene=f"CAND{i}", hgvs="c.1A>G") for i in range(n_candidates)]
        return data_layer.DataLayerResult(case_id=case.case_id, variants=variants)

    monkeypatch.setattr(data_layer, "run", _fake_data_layer_run)


# --------------------------------------------------------------------------- #
# Gate ON: raw records over cap, reduced set within cap -> NOT rejected
# --------------------------------------------------------------------------- #
def test_gate_on_large_vcf_reduced_under_cap_is_accepted(client, monkeypatch):
    monkeypatch.setattr(settings, "FACILITY_DATA_LAYER_GATE", True)
    # Raw file has 500 records (>> cap of 50) but the data layer funnels it to 5 candidates.
    _stub_reduction(monkeypatch, n_candidates=5)

    full_key, _ = api_keys.generate_key("Facility")
    r = client.post(
        "/api/v1/analyze",
        data={"case_id": "T-GATE-ON", "clinical_summary": "Large VCF, gated."},
        files={"vcf": ("huge.vcf", _big_vcf(500), "text/plain")},
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 200, r.text
    # variant_count reflects the reduced candidate set (vcf_path cleared => no +1 for file).
    assert r.json()["variant_count"] == 5
    # The pipeline must receive the REDUCED variants with vcf_path cleared (no double gate).
    case = client.captured["case"]  # type: ignore[attr-defined]
    assert len(case.variants) == 5
    assert case.vcf_path is None


# --------------------------------------------------------------------------- #
# Gate OFF: raw-record cap still returns 413 (unchanged behavior)
# --------------------------------------------------------------------------- #
def test_gate_off_large_vcf_still_rejected_on_raw_count(client, monkeypatch):
    monkeypatch.setattr(settings, "FACILITY_DATA_LAYER_GATE", False)
    # Even if a reduction WOULD shrink it, the gate is off so it must not run.
    _stub_reduction(monkeypatch, n_candidates=5)

    full_key, _ = api_keys.generate_key("Facility")
    r = client.post(
        "/api/v1/analyze",
        data={"case_id": "T-GATE-OFF", "clinical_summary": "Large VCF, not gated."},
        files={"vcf": ("huge.vcf", _big_vcf(60), "text/plain")},
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 413, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "variant_cap_exceeded"
    assert detail["submitted_variants"] == 60  # raw record count, not reduced
    assert detail["max_variants_per_request"] == 50
    assert "Research use only" in detail["notice"]


# --------------------------------------------------------------------------- #
# Gate ON but reduced set STILL over cap -> 413 shape preserved on reduced count
# --------------------------------------------------------------------------- #
def test_gate_on_reduced_still_over_cap_returns_413(client, monkeypatch):
    monkeypatch.setattr(settings, "FACILITY_DATA_LAYER_GATE", True)
    _stub_reduction(monkeypatch, n_candidates=51)  # reduced count still exceeds cap of 50

    full_key, _ = api_keys.generate_key("Facility")
    r = client.post(
        "/api/v1/analyze",
        data={"case_id": "T-GATE-ON-OVER", "clinical_summary": "Reduced still over cap."},
        files={"vcf": ("huge.vcf", _big_vcf(500), "text/plain")},
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 413, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "variant_cap_exceeded"
    assert detail["submitted_variants"] == 51  # measured on the REDUCED candidate set
    assert detail["max_variants_per_request"] == 50
    assert "Research use only" in detail["notice"]


# --------------------------------------------------------------------------- #
# Gate ON but reduction raises -> fail safe to raw-record cap
# --------------------------------------------------------------------------- #
def test_gate_on_reduction_failure_falls_back_to_raw_cap(client, monkeypatch):
    monkeypatch.setattr(settings, "FACILITY_DATA_LAYER_GATE", True)

    def _boom(case, config=None):
        raise RuntimeError("data layer blew up")

    monkeypatch.setattr(data_layer, "run", _boom)

    full_key, _ = api_keys.generate_key("Facility")
    r = client.post(
        "/api/v1/analyze",
        data={"case_id": "T-GATE-FAIL", "clinical_summary": "Reduction fails."},
        files={"vcf": ("huge.vcf", _big_vcf(60), "text/plain")},
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 413, r.text
    detail = r.json()["detail"]
    assert detail["submitted_variants"] == 60  # fell back to raw record count


# --------------------------------------------------------------------------- #
# No-VCF structured case is identical regardless of the facility gate flag
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("gate", [True, False])
def test_no_vcf_case_unaffected_by_gate(client, monkeypatch, gate):
    monkeypatch.setattr(settings, "FACILITY_DATA_LAYER_GATE", gate)
    # If the gate wrongly engaged without a VCF this stub would change the count.
    _stub_reduction(monkeypatch, n_candidates=999)

    full_key, _ = api_keys.generate_key("Facility")
    body = {
        "case_id": "T-NOVCF",
        "clinical_summary": "Structured variants only.",
        "variants": [{"gene": f"GENE{i}", "hgvs": "c.1A>G"} for i in range(3)],
    }
    r = client.post("/api/v1/analyze", json=body,
                    headers={"X-API-Key": full_key})
    assert r.status_code == 200, r.text
    assert r.json()["variant_count"] == 3  # gate never engages without a vcf_path
