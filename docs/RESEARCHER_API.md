# Navigator Genome Pilot — Researcher API (`/api/v1`)

> **RESEARCH USE ONLY.** Navigator Genome Pilot is a research tool. Every output is a
> **research hypothesis with explicit uncertainty — it is not a diagnosis and not medical
> advice.** Results must be independently reviewed and confirmed by qualified
> professionals before any clinical interpretation. Do not use this API for patient care.

This guide is for research facilities that want to submit cases and retrieve evidence
dossiers programmatically. The interactive web demo (`/`, `/lab`) remains open and
unchanged; this authenticated API is a separate, versioned namespace.

Base URL (production): `https://navigator-genome.abacusai.cloud`

---

## 1. Getting an API key

The platform issues **one API key per research facility**. Keys are created by the
maintainer with a short command-line tool and handed to the facility over a secure
channel.

- Contact the maintainer to request access for your facility, **or** if you operate the
  deployment, issue a key yourself:

  ```bash
  /opt/abacus-python/bin/python3 scripts/manage_api_keys.py issue --label "Your Facility Name"
  ```

  This prints the full key **exactly once**:

  ```
  Full API key (send as the X-API-Key header):

      nvk_ae139e22_fFdIDzk9CFlcr8GeXgRxmfLN8YBrtq4h1-ar6RHvjy8
  ```

- **Store it securely.** The platform keeps only a *salted SHA-256 hash* of the secret —
  the plaintext is never stored and cannot be recovered. A lost key can only be revoked
  and re-issued.

Key management commands (maintainer):

| Command | Purpose |
|---|---|
| `manage_api_keys.py issue --label "Name" [limit flags]` | Issue a new key for a facility (prints it once). Optional per-key limit flags — see §5.5. |
| `manage_api_keys.py list` | List keys: `key_id`, label, created, active, limit overrides — **never secrets**. |
| `manage_api_keys.py inspect --key-id nvk_xxxxxxxx` | Show one key's details and **effective limits** (overrides + defaults). |
| `manage_api_keys.py revoke --key-id nvk_xxxxxxxx` | Revoke a key immediately. |

---

## 2. Authentication

Send your full key in the **`X-API-Key`** request header on every `/api/v1/*` call:

```
X-API-Key: nvk_ae139e22_fFdIDzk9CFlcr8GeXgRxmfLN8YBrtq4h1-ar6RHvjy8
```

Responses:

- **401 Unauthorized** — the `X-API-Key` header is missing.
- **403 Forbidden** — the key is unknown or has been revoked.
- Verification is constant-time; only the `key_id` prefix is used for lookup, and the
  secret is compared against its salted hash.

> Authentication can be toggled with the `API_KEYS_REQUIRED` environment variable
> (default **on**). It is intended to stay on in production.

---

## 3. Endpoints

All endpoints below require a valid `X-API-Key` header.

### `GET /api/v1/me`
Returns the authenticated facility's identity and its **effective throttling limits**
(never the secret). `limits` is what is actually enforced for your key (per-key overrides
merged over the global defaults); `limit_overrides` shows only the fields your key
overrides (empty means you use every global default).

```json
{
  "key_id": "nvk_ae139e22",
  "label": "Your Facility Name",
  "active": true,
  "limits": {
    "max_variants_per_request": 50000,
    "requests_per_minute": 10,
    "requests_per_day": 200,
    "max_concurrent": 2
  },
  "limit_overrides": {},
  "notice": "Research use only. Outputs are research hypotheses with explicit uncertainty — not a diagnosis and not medical advice."
}
```

Call this first to discover the limits your facility has been granted before sizing your
submissions.

### `GET /api/v1/cases`
Lists the bundled benchmark cases available in this deployment.

```json
{ "cases": [ { "file": "cf_cftr.json", "case_id": "CF-CFTR-F508del", "summary": "..." } ] }
```

### `POST /api/v1/analyze`
Runs the 8-agent research pipeline on a submitted case and returns the full result
(agent results + ranked evidence dossier). Accepts **either** JSON **or**
multipart/form-data (for VCF upload).

**JSON body fields**

| Field | Type | Notes |
|---|---|---|
| `case_id` | string | Optional; auto-generated if omitted. Sanitized for safe storage. |
| `clinical_summary` | string | Free-text clinical picture. |
| `hpo_terms` | list[string] *or* string | HPO terms; a string may be comma/newline separated. |
| `variants` | list[object] *or* string | Each object: `gene`, `hgvs`, `chrom`, `pos`, `ref`, `alt`, `rsid` (only `gene` required). A string is parsed one variant per line. |

You must provide **at least one** of `clinical_summary`, `variants`, or a VCF file,
otherwise the call returns **400**.

**multipart/form-data fields:** `case_id`, `clinical_summary`, `hpo_terms`,
`variants` (text), and an optional **`vcf`** file (`.vcf` / `.vcf.gz`, ≤ 25 MB).

**Response** (same shape as the web demo's `/run`, plus `variant_count`):

```json
{
  "case_id": "T-API-1",
  "status": "ok",
  "provider": "dev",
  "variant_count": 1,
  "dossier": { "findings": [ /* ranked research hypotheses with uncertainty labels */ ] },
  "agent_results": [ /* per-agent evidence */ ]
}
```

### `GET /api/v1/dossier/{case_id}`
Downloads the rendered dossier **PDF** for a case that has already been analyzed.
Returns **404** if no dossier exists yet for that `case_id` (run `/analyze` first).

---

## 4. Examples

### curl — analyze (JSON)

```bash
curl -s -X POST https://navigator-genome.abacusai.cloud/api/v1/analyze \
  -H "X-API-Key: $NAVIGATOR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "case_id": "FAC-001",
        "clinical_summary": "Infant with recurrent respiratory infections and failure to thrive.",
        "hpo_terms": ["Recurrent respiratory infections", "Failure to thrive"],
        "variants": [{"gene": "CFTR", "hgvs": "c.1521_1523del"}]
      }'
```

### curl — analyze (VCF upload)

```bash
curl -s -X POST https://navigator-genome.abacusai.cloud/api/v1/analyze \
  -H "X-API-Key: $NAVIGATOR_API_KEY" \
  -F "case_id=FAC-002" \
  -F "clinical_summary=Suspected rare metabolic disorder." \
  -F "hpo_terms=Seizures, Developmental delay" \
  -F "vcf=@/path/to/sample.vcf"
```

### curl — download the dossier PDF

```bash
curl -s -o dossier_FAC-001.pdf \
  -H "X-API-Key: $NAVIGATOR_API_KEY" \
  https://navigator-genome.abacusai.cloud/api/v1/dossier/FAC-001
```

### Python (`requests`) — analyze (JSON) + download dossier

```python
import requests

BASE = "https://navigator-genome.abacusai.cloud"
HEADERS = {"X-API-Key": "nvk_ae139e22_...your-secret..."}

# 1) Submit a case as JSON
payload = {
    "case_id": "FAC-001",
    "clinical_summary": "Infant with recurrent respiratory infections and failure to thrive.",
    "hpo_terms": ["Recurrent respiratory infections", "Failure to thrive"],
    "variants": [{"gene": "CFTR", "hgvs": "c.1521_1523del"}],
}
r = requests.post(f"{BASE}/api/v1/analyze", json=payload, headers=HEADERS, timeout=600)
r.raise_for_status()
result = r.json()
print("variant_count:", result["variant_count"])
print("top findings:", result.get("dossier", {}).get("findings", [])[:1])

# 2) Download the rendered dossier PDF
pdf = requests.get(f"{BASE}/api/v1/dossier/{payload['case_id']}", headers=HEADERS, timeout=120)
pdf.raise_for_status()
open("dossier_FAC-001.pdf", "wb").write(pdf.content)
```

### Python (`requests`) — analyze with a VCF upload

```python
import requests

BASE = "https://navigator-genome.abacusai.cloud"
HEADERS = {"X-API-Key": "nvk_ae139e22_...your-secret..."}

with open("sample.vcf", "rb") as fh:
    r = requests.post(
        f"{BASE}/api/v1/analyze",
        headers=HEADERS,
        data={
            "case_id": "FAC-002",
            "clinical_summary": "Suspected rare metabolic disorder.",
            "hpo_terms": "Seizures, Developmental delay",
        },
        files={"vcf": ("sample.vcf", fh, "text/plain")},
        timeout=600,
    )
r.raise_for_status()
print(r.json()["case_id"], r.json()["variant_count"])
```

---

## 5. Limits, quotas & throttling

To protect shared processing capacity (there can be a large analysis backlog), the
authenticated API enforces several **per-API-key** limits. These apply **only** to the
`/api/v1` endpoints — the public web demo (`/`, `/run`, `/lab`) is never throttled. Each
limit has a global default and can be raised or lowered per facility (see your effective
values via `GET /api/v1/me`).

| Limit | Default | Applies to | On exceed |
|---|---|---|---|
| **VCF upload size** | 25 MB | `/analyze` uploads | **413** |
| **Variants per request** | 50,000 | `/analyze` | **413** |
| **Requests per minute** | 10 | `/analyze` (writes) | **429** + `Retry-After` |
| **Requests per day** | 200 | `/analyze` (writes) | **429** + `Retry-After` |
| **Concurrent analyses** | 2 | `/analyze` | **429** + `Retry-After` |

Read endpoints (`/me`, `/cases`, `/dossier/{case_id}`) are **not** rate-limited or
concurrency-limited — only the expensive `/analyze` endpoint is. Still authenticate them
with your key.

### 5.1 Per-request variant cap → `413`

`/analyze` rejects a submission whose variant count exceeds your `max_variants_per_request`
(default **50,000**). The count is:

- **VCF uploads:** the number of **data (non-header) records** (lines not starting with `#`).
- **JSON / text variant lists:** the number of entries.

The 25 MB upload cap still applies independently (also returns **413**). Response body:

```json
{
  "detail": {
    "error": "variant_cap_exceeded",
    "message": "Submission has 73120 variants, which exceeds the per-request cap of 50000 for this API key. Split the work into smaller batches of at most 50000 variants and submit them sequentially.",
    "submitted_variants": 73120,
    "max_variants_per_request": 50000,
    "notice": "Research use only. ..."
  }
}
```

**How to handle it:** split a large genome/variant set into batches of at most your cap
and submit them as separate cases, sequentially.

### 5.2 Per-key rate limits → `429`

Each key may make at most `requests_per_minute` (default **10**) and `requests_per_day`
(default **200**) calls to `/analyze`, measured as **sliding windows**. When you exceed
either, you get **429** with a `Retry-After` header (whole seconds until the window frees):

```
HTTP/1.1 429 Too Many Requests
Retry-After: 42
X-RateLimit-Limit-Minute: 10
X-RateLimit-Remaining-Minute: 0
X-RateLimit-Limit-Day: 200
X-RateLimit-Remaining-Day: 143
```
```json
{
  "detail": {
    "error": "rate_limit_exceeded",
    "message": "Rate limit exceeded for this API key: 10 requests/minute, 200 requests/day. Retry in about 42s, or slow your submission rate and batch work sequentially.",
    "retry_after_seconds": 42,
    "limit_per_minute": 10,
    "limit_per_day": 200,
    "notice": "Research use only. ..."
  }
}
```

Successful `/analyze` responses also carry the `X-RateLimit-*` headers so you can track
your remaining budget and pace yourself before hitting a 429.

### 5.3 Max concurrent analyses → `429`

A key may have at most `max_concurrent` (default **2**) `/analyze` runs in flight at once.
A further concurrent call returns **429** with a `Retry-After` (an estimate — wait for one
of your running analyses to finish):

```json
{
  "detail": {
    "error": "concurrency_limit_exceeded",
    "message": "This API key already has 2 analysis run(s) in progress (the maximum). Wait for one to finish before submitting another, then retry.",
    "retry_after_seconds": 15,
    "max_concurrent": 2,
    "notice": "Research use only. ..."
  }
}
```

### 5.4 Recommended client behaviour (back off & batch)

- **Submit sequentially**, not in bursts. Keep in-flight `/analyze` calls at or below your
  `max_concurrent`.
- **Honour `Retry-After`.** On a **429**, sleep for the header's seconds (add a little
  jitter) and retry; do not hammer the endpoint.
- **Batch large inputs.** On a **413**, split variants into batches ≤ your
  `max_variants_per_request` and submit them as separate cases.
- **Watch the `X-RateLimit-Remaining-*` headers** and slow down as they approach 0.
- **Use a generous timeout.** `/analyze` runs the full 8-agent pipeline and may take tens
  of seconds to a few minutes per case.
- **Content types:** `/analyze` accepts `application/json` or `multipart/form-data` only;
  other content types return **400**.

Minimal Python back-off example:

```python
import time, requests

def analyze_with_backoff(base, headers, payload, max_tries=5):
    for attempt in range(max_tries):
        r = requests.post(f"{base}/api/v1/analyze", json=payload, headers=headers, timeout=600)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "30"))
            time.sleep(wait + 1)
            continue
        if r.status_code == 413:
            raise ValueError(r.json()["detail"]["message"])  # split your batch and resubmit
        r.raise_for_status()
        return r.json()
    raise RuntimeError("giving up after repeated rate-limit responses")
```

### 5.5 Per-facility limit tiers (maintainer)

Limits can be set per key at issue time; any flag omitted uses the global default from
`config/settings.py`:

```bash
/opt/abacus-python/bin/python3 scripts/manage_api_keys.py issue \
  --label "High-throughput Facility" \
  --requests-per-minute 30 \
  --requests-per-day 2000 \
  --max-concurrent 4 \
  --max-variants-per-request 100000
```

Inspect a key's effective limits (overrides merged over defaults):

```bash
/opt/abacus-python/bin/python3 scripts/manage_api_keys.py inspect --key-id nvk_xxxxxxxx
```

`manage_api_keys.py list` also shows each key's limit overrides.

### 5.6 Scaling note (operations)

The rate-limit and in-flight counters are **per process** (per uvicorn worker). The current
deployment runs a single worker, so the limits above are global. If the service is scaled
to multiple workers or hosts, each worker would track counts independently and the
effective limit would multiply by the worker count; to keep limits truly global in that
setup, move the counters to a shared store such as **Redis** (see `src/utils/throttle.py`
for the designated swap point).

## 6. Security

- Keys are stored **only as salted SHA-256 hashes** (per-key random salt) — the plaintext
  secret is never written to disk and cannot be recovered.
- Compromised or rotated keys can be **revoked instantly**
  (`manage_api_keys.py revoke --key-id nvk_xxxxxxxx`); revoked keys immediately fail
  verification with **403**.
- Send keys over secure channels only, and transmit all API traffic over HTTPS.

---

*Navigator Genome Pilot is a research project. Outputs are hypotheses for research review,
not clinical conclusions.*
