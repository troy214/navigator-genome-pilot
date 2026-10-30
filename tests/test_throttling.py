"""Offline tests for the researcher API throttling / quota controls (/api/v1).

No live LLM/HTTP calls: Coordinator.run is monkeypatched. The key store is redirected
to a tmp file per test and the in-process throttler is reset before each test so counts
never leak between tests.

Covers:
  * per-request variant cap rejection (413) for JSON and VCF submissions
  * per-minute rate limit -> 429 with Retry-After
  * per-key concurrency limit -> 429 with Retry-After (slot always released)
  * per-key override precedence over global defaults
  * /api/v1/me surfaces effective limits
  * public demo endpoints remain unthrottled + unauthenticated
  * the sliding-window / concurrency unit logic in src/utils/throttle.py
"""
from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from config import settings
from src.utils import api_keys
from src.utils.throttle import Throttler, effective_limits, throttler


@pytest.fixture(autouse=True)
def _tmp_store_and_reset(tmp_path, monkeypatch):
    """Throwaway key store, auth ON, generous global defaults, fresh throttler."""
    store = tmp_path / "api_keys.json"
    monkeypatch.setattr(settings, "API_KEYS_STORE", str(store))
    monkeypatch.setattr(settings, "API_KEYS_REQUIRED", True)
    # Predictable global defaults for the tests.
    monkeypatch.setattr(settings, "API_MAX_VARIANTS_PER_REQUEST", 50)
    monkeypatch.setattr(settings, "API_REQUESTS_PER_MINUTE", 3)
    monkeypatch.setattr(settings, "API_REQUESTS_PER_DAY", 1000)
    monkeypatch.setattr(settings, "API_MAX_CONCURRENT_ANALYSES", 2)
    throttler.reset()
    yield store
    throttler.reset()


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


def _analyze_body(n_variants: int) -> dict:
    return {
        "case_id": "T-THROTTLE",
        "clinical_summary": "Research hypothesis submission.",
        "variants": [{"gene": f"GENE{i}", "hgvs": "c.1A>G"} for i in range(n_variants)],
    }


# --------------------------------------------------------------------------- #
# 1) Per-request variant cap
# --------------------------------------------------------------------------- #
def test_variant_cap_rejects_json_over_limit(client):
    full_key, _ = api_keys.generate_key("Facility")
    r = client.post("/api/v1/analyze", json=_analyze_body(51),
                    headers={"X-API-Key": full_key})
    assert r.status_code == 413, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "variant_cap_exceeded"
    assert detail["submitted_variants"] == 51
    assert detail["max_variants_per_request"] == 50


def test_variant_cap_allows_at_limit(client):
    full_key, _ = api_keys.generate_key("Facility")
    r = client.post("/api/v1/analyze", json=_analyze_body(50),
                    headers={"X-API-Key": full_key})
    assert r.status_code == 200, r.text
    assert r.json()["variant_count"] == 50


def test_variant_cap_counts_vcf_data_records(client):
    full_key, _ = api_keys.generate_key("Facility")
    # 51 data records + header lines -> exceeds cap of 50.
    data_lines = "".join(f"7\t{1000 + i}\t.\tA\tG\n" for i in range(51))
    vcf = ("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\n" + data_lines).encode()
    r = client.post(
        "/api/v1/analyze",
        data={"case_id": "T-VCF-CAP", "clinical_summary": "VCF over cap."},
        files={"vcf": ("big.vcf", vcf, "text/plain")},
        headers={"X-API-Key": full_key},
    )
    assert r.status_code == 413, r.text
    assert r.json()["detail"]["submitted_variants"] == 51


# --------------------------------------------------------------------------- #
# 2) Per-minute rate limit
# --------------------------------------------------------------------------- #
def test_per_minute_rate_limit_429(client):
    full_key, _ = api_keys.generate_key("Facility")
    headers = {"X-API-Key": full_key}
    body = _analyze_body(1)
    # Default rpm = 3: first three pass, fourth is blocked.
    for _ in range(3):
        assert client.post("/api/v1/analyze", json=body, headers=headers).status_code == 200
    r = client.post("/api/v1/analyze", json=body, headers=headers)
    assert r.status_code == 429, r.text
    assert r.headers.get("Retry-After") is not None
    assert int(r.headers["Retry-After"]) >= 1
    detail = r.json()["detail"]
    assert detail["error"] == "rate_limit_exceeded"
    assert detail["limit_per_minute"] == 3


def test_ratelimit_headers_present_on_success(client):
    full_key, _ = api_keys.generate_key("Facility")
    r = client.post("/api/v1/analyze", json=_analyze_body(1),
                    headers={"X-API-Key": full_key})
    assert r.status_code == 200
    assert r.headers.get("X-RateLimit-Limit-Minute") == "3"
    assert r.headers.get("X-RateLimit-Remaining-Minute") == "2"


# --------------------------------------------------------------------------- #
# 3) Concurrency limit
# --------------------------------------------------------------------------- #
def test_concurrency_limit_429(client, monkeypatch):
    """Hold the throttler's slots full, then a new /analyze gets 429."""
    full_key, rec = api_keys.generate_key("Facility")
    key_id = rec["key_id"]
    # Simulate 2 in-flight analyses (the default max) for this key.
    assert throttler.acquire(key_id, 2) is True
    assert throttler.acquire(key_id, 2) is True
    r = client.post("/api/v1/analyze", json=_analyze_body(1),
                    headers={"X-API-Key": full_key})
    assert r.status_code == 429, r.text
    assert r.headers.get("Retry-After") is not None
    detail = r.json()["detail"]
    assert detail["error"] == "concurrency_limit_exceeded"
    assert detail["max_concurrent"] == 2
    # Release and confirm a call now succeeds (slot bookkeeping is correct).
    throttler.release(key_id)
    throttler.release(key_id)
    assert client.post("/api/v1/analyze", json=_analyze_body(1),
                       headers={"X-API-Key": full_key}).status_code == 200


def test_concurrency_slot_released_after_each_call(client):
    """Sequential calls under the per-minute limit must not exhaust concurrency slots."""
    full_key, rec = api_keys.generate_key("Facility")
    for _ in range(3):
        assert client.post("/api/v1/analyze", json=_analyze_body(1),
                           headers={"X-API-Key": full_key}).status_code == 200
    assert throttler.in_flight(rec["key_id"]) == 0


# --------------------------------------------------------------------------- #
# 4) Per-key override precedence
# --------------------------------------------------------------------------- #
def test_per_key_override_beats_default(client):
    # Give this key a higher variant cap than the global default of 50.
    full_key, _ = api_keys.generate_key(
        "Premium Facility", limits={"max_variants_per_request": 100})
    # 60 variants would exceed the global default (50) but is under this key's 100.
    r = client.post("/api/v1/analyze", json=_analyze_body(60),
                    headers={"X-API-Key": full_key})
    assert r.status_code == 200, r.text
    assert r.json()["variant_count"] == 60


def test_per_key_lower_rpm_override(client):
    full_key, _ = api_keys.generate_key(
        "Restricted Facility", limits={"requests_per_minute": 1})
    headers = {"X-API-Key": full_key}
    assert client.post("/api/v1/analyze", json=_analyze_body(1), headers=headers).status_code == 200
    r = client.post("/api/v1/analyze", json=_analyze_body(1), headers=headers)
    assert r.status_code == 429
    assert r.json()["detail"]["limit_per_minute"] == 1


def test_effective_limits_merges_overrides():
    rec = {"limits": {"requests_per_minute": 99}}
    eff = effective_limits(rec)
    assert eff["requests_per_minute"] == 99          # override
    assert eff["requests_per_day"] == 1000           # global default
    assert eff["max_variants_per_request"] == 50     # global default
    assert eff["max_concurrent"] == 2                # global default


def test_effective_limits_ignores_bad_overrides():
    rec = {"limits": {"requests_per_minute": 0, "max_concurrent": -3}}
    eff = effective_limits(rec)
    assert eff["requests_per_minute"] == 3           # falls back (0 ignored)
    assert eff["max_concurrent"] == 2                # falls back (negative ignored)


# --------------------------------------------------------------------------- #
# 5) /api/v1/me surfaces effective limits
# --------------------------------------------------------------------------- #
def test_me_shows_effective_limits(client):
    full_key, _ = api_keys.generate_key(
        "Facility", limits={"max_concurrent": 5})
    r = client.get("/api/v1/me", headers={"X-API-Key": full_key})
    assert r.status_code == 200
    body = r.json()
    assert body["limits"]["max_concurrent"] == 5             # override surfaced
    assert body["limits"]["requests_per_minute"] == 3        # default surfaced
    assert body["limit_overrides"] == {"max_concurrent": 5}


# --------------------------------------------------------------------------- #
# 6) Public demo endpoints stay unthrottled + unauthenticated
# --------------------------------------------------------------------------- #
def test_public_endpoints_unthrottled(client, monkeypatch):
    """Hammer /run and /cases well past the API rate limit — all succeed, no key."""
    from app.backend import main

    monkeypatch.setattr(main.Coordinator, "run",
                        lambda self, case: {"case_id": case.case_id, "status": "ok"})
    # /cases and /health are public and should never 401/429.
    for _ in range(20):
        assert client.get("/cases").status_code == 200
        assert client.get("/health").status_code == 200
    # /run (public) many times — the /api/v1 rpm limit of 3 must not apply.
    body = {"case_id": "PUB-1", "clinical_summary": "x", "variants": []}
    for _ in range(10):
        assert client.post("/run", json=body).status_code == 200


# --------------------------------------------------------------------------- #
# 7) Read endpoints are exempt from the analyze rate limit
# --------------------------------------------------------------------------- #
def test_read_endpoints_not_rate_limited(client):
    full_key, _ = api_keys.generate_key("Facility")
    headers = {"X-API-Key": full_key}
    # Far more than rpm=3 read calls — none should be throttled.
    for _ in range(10):
        assert client.get("/api/v1/me", headers=headers).status_code == 200
        assert client.get("/api/v1/cases", headers=headers).status_code == 200


# --------------------------------------------------------------------------- #
# 8) Throttler unit logic
# --------------------------------------------------------------------------- #
def test_throttler_sliding_window_unit():
    t = Throttler()
    t0 = 1000.0
    # rpm=2, rpd=100. Two allowed, third blocked within the minute.
    assert t.check_rate("k", 2, 100, now=t0).allowed is True
    assert t.check_rate("k", 2, 100, now=t0 + 1).allowed is True
    d = t.check_rate("k", 2, 100, now=t0 + 2)
    assert d.allowed is False
    assert d.retry_after >= 1
    # After the minute window passes, requests are allowed again.
    assert t.check_rate("k", 2, 100, now=t0 + 61).allowed is True


def test_throttler_concurrency_unit():
    t = Throttler()
    assert t.acquire("k", 2) is True
    assert t.acquire("k", 2) is True
    assert t.acquire("k", 2) is False      # at max
    t.release("k")
    assert t.acquire("k", 2) is True       # slot freed
    # release never goes negative
    t.release("k")
    t.release("k")
    t.release("k")
    assert t.in_flight("k") == 0


def test_throttler_thread_safety_smoke():
    """Concurrent acquires never exceed the max slot count."""
    t = Throttler()
    max_slots = 5
    successes = []
    lock = threading.Lock()

    def worker():
        if t.acquire("k", max_slots):
            with lock:
                successes.append(1)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert sum(successes) == max_slots
