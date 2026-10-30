"""Offline tests for the researcher-facing, API-key-authenticated /api/v1 namespace.

No live LLM/HTTP calls: Coordinator.run is monkeypatched. The key store is redirected
to a tmp file per test so nothing touches the real data/api_keys.json.

Covers:
  (a) a generated key verifies; a tampered/unknown key does not
  (b) a revoked key fails verification
  (c) /api/v1/analyze -> 401 (no key), 403 (bad key), 200 (valid key, mocked pipeline)
  (d) manage_api_keys issue -> list -> revoke round-trip
  (e) hashed secrets are never stored in plaintext in data/api_keys.json
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from config import settings
from src.utils import api_keys


@pytest.fixture(autouse=True)
def _tmp_store(tmp_path, monkeypatch):
    """Point the key store at a throwaway file and force auth ON for every test."""
    store = tmp_path / "api_keys.json"
    monkeypatch.setattr(settings, "API_KEYS_STORE", str(store))
    monkeypatch.setattr(settings, "API_KEYS_REQUIRED", True)
    # Keep the facility data-layer gate OFF here so the existing VCF tests exercise the
    # raw-record path deterministically and offline (no data-layer / network annotation).
    # The gate-ON reduction behavior is covered by tests/test_data_layer_gate_cap.py.
    monkeypatch.setattr(settings, "FACILITY_DATA_LAYER_GATE", False)
    return store


@pytest.fixture
def client(monkeypatch):
    """TestClient with a mocked pipeline so /api/v1/analyze never calls a model."""
    from app.backend import main

    def _fake_run(self, case):
        return {
            "case_id": case.case_id,
            "status": "ok",
            "provider": "dev",
            "dossier": {"findings": []},
            "agent_results": [],
        }

    monkeypatch.setattr(main.Coordinator, "run", _fake_run)
    return TestClient(main.app)


# --------------------------------------------------------------------------- #
# (a) + (b) key verification
# --------------------------------------------------------------------------- #
def test_generated_key_verifies():
    full_key, rec = api_keys.generate_key("Acme Research Lab")
    verified = api_keys.verify_key(full_key)
    assert verified is not None
    assert verified["key_id"] == rec["key_id"]


def test_tampered_key_fails():
    full_key, _ = api_keys.generate_key("Acme Research Lab")
    tampered = full_key[:-1] + ("x" if full_key[-1] != "x" else "y")
    assert api_keys.verify_key(tampered) is None


def test_unknown_key_fails():
    api_keys.generate_key("Acme Research Lab")
    assert api_keys.verify_key("nvk_deadbeef_totallybogussecret") is None
    assert api_keys.verify_key("not-even-a-key") is None
    assert api_keys.verify_key("") is None


def test_revoked_key_fails():
    full_key, rec = api_keys.generate_key("Acme Research Lab")
    assert api_keys.verify_key(full_key) is not None
    assert api_keys.revoke_key(rec["key_id"]) is True
    assert api_keys.verify_key(full_key) is None


# --------------------------------------------------------------------------- #
# (c) endpoint auth behaviour
# --------------------------------------------------------------------------- #
_ANALYZE_BODY = {
    "case_id": "T-API-1",
    "clinical_summary": "Test clinical summary for a research hypothesis.",
    "hpo_terms": ["Seizures", "Developmental delay"],
    "variants": [{"gene": "CFTR", "hgvs": "c.1521_1523del"}],
}


def test_analyze_401_without_key(client):
    r = client.post("/api/v1/analyze", json=_ANALYZE_BODY)
    assert r.status_code == 401


def test_analyze_403_with_bad_key(client):
    r = client.post("/api/v1/analyze", json=_ANALYZE_BODY,
                    headers={"X-API-Key": "nvk_deadbeef_bogus"})
    assert r.status_code == 403


def test_analyze_200_with_valid_key_json(client):
    full_key, _ = api_keys.generate_key("Acme Research Lab")
    r = client.post("/api/v1/analyze", json=_ANALYZE_BODY,
                    headers={"X-API-Key": full_key})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["case_id"] == "T-API-1"
    assert data["variant_count"] == 1


def test_analyze_200_with_valid_key_multipart(client):
    full_key, _ = api_keys.generate_key("Acme Research Lab")
    r = client.post(
        "/api/v1/analyze",
        data={"case_id": "T-API-2",
              "clinical_summary": "Symptom-only submission.",
              "hpo_terms": "Seizures\nAtaxia",
              "variants": "CFTR c.1521_1523del"},
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 200, r.text
    assert r.json()["case_id"] == "T-API-2"


def test_analyze_with_vcf_upload(client):
    full_key, _ = api_keys.generate_key("Acme Research Lab")
    vcf = b"##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\n7\t117530975\t.\tA\tG\n"
    r = client.post(
        "/api/v1/analyze",
        data={"case_id": "T-API-VCF", "clinical_summary": "With VCF."},
        files={"vcf": ("sample.vcf", vcf, "text/plain")},
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 200, r.text
    assert r.json()["variant_count"] >= 1


def test_analyze_400_empty_submission(client):
    full_key, _ = api_keys.generate_key("Acme Research Lab")
    r = client.post("/api/v1/analyze", json={"case_id": "T-empty"},
                    headers={"X-API-Key": full_key})
    assert r.status_code == 400


def test_me_and_cases_behind_key(client):
    full_key, rec = api_keys.generate_key("Acme Research Lab")
    # /me
    r = client.get("/api/v1/me", headers={"X-API-Key": full_key})
    assert r.status_code == 200
    body = r.json()
    assert body["key_id"] == rec["key_id"]
    assert body["label"] == "Acme Research Lab"
    assert "secret" not in json.dumps(body).lower() or "research" in body["notice"].lower()
    # /cases
    r = client.get("/api/v1/cases", headers={"X-API-Key": full_key})
    assert r.status_code == 200
    assert "cases" in r.json()
    # no key -> 401
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/cases").status_code == 401


def test_public_endpoints_stay_open(client):
    """The demo endpoints must NOT require a key."""
    assert client.get("/health").status_code == 200
    assert client.get("/cases").status_code == 200


# --------------------------------------------------------------------------- #
# (d) CLI round-trip
# --------------------------------------------------------------------------- #
def test_cli_issue_list_revoke_roundtrip(capsys):
    from scripts import manage_api_keys as cli

    # issue
    assert cli.main(["issue", "--label", "CLI Facility"]) == 0
    out = capsys.readouterr().out
    assert "nvk_" in out and "API KEY ISSUED" in out
    # extract the full key printed in the issue block
    full_key = next(tok for line in out.splitlines()
                    for tok in line.split() if tok.startswith("nvk_") and "_" in tok[4:])
    assert api_keys.verify_key(full_key) is not None
    key_id = api_keys.list_keys()[0]["key_id"]

    # list
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert key_id in out and "CLI Facility" in out

    # revoke
    assert cli.main(["revoke", "--key-id", key_id]) == 0
    out = capsys.readouterr().out
    assert "Revoked" in out
    assert api_keys.verify_key(full_key) is None


# --------------------------------------------------------------------------- #
# (e) secrets never persisted in plaintext
# --------------------------------------------------------------------------- #
def test_secret_never_stored_plaintext(_tmp_store):
    full_key, _ = api_keys.generate_key("Acme Research Lab")
    secret = full_key.split("_", 2)[2]
    raw = _tmp_store.read_text()
    assert secret not in raw
    records = json.loads(raw)
    for rec in records:
        assert "hashed_secret" in rec and "salt" in rec
        assert rec["hashed_secret"] != secret
        # no field accidentally holds the plaintext secret
        assert secret not in json.dumps(rec)
