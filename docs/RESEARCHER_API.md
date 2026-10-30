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
| `manage_api_keys.py issue --label "Name"` | Issue a new key for a facility (prints it once). |
| `manage_api_keys.py list` | List keys: `key_id`, label, created, active — **never secrets**. |
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
Returns the authenticated facility's identity (never the secret).

```json
{
  "key_id": "nvk_ae139e22",
  "label": "Your Facility Name",
  "active": true,
  "notice": "Research use only. Outputs are research hypotheses with explicit uncertainty — not a diagnosis and not medical advice."
}
```

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

## 5. Limits & operational notes

- **VCF upload size:** ≤ **25 MB** (`.vcf` or `.vcf.gz`). Larger uploads return **413**;
  the same cap is enforced at the web server.
- **Analysis latency:** `/api/v1/analyze` runs the full 8-agent pipeline and may take
  tens of seconds to a few minutes. Use a generous client timeout and submit cases
  sequentially rather than in large bursts.
- **Content types:** `/api/v1/analyze` accepts `application/json` or
  `multipart/form-data` only; other content types return **400**.

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
