# Navigator Genome Pilot — Facility Integration (for Meta)

> **RESEARCH USE ONLY.** Navigator Genome Pilot is a research tool. Every output is a
> **research hypothesis with explicit uncertainty — not a diagnosis and not medical
> advice.** Results must be independently reviewed and confirmed by qualified
> professionals before any clinical interpretation.

**Live demo:** https://navigator-genome.abacusai.cloud · **Repo:** https://github.com/troy214/navigator-genome-pilot (private)

---

## What Navigator is

An 8-agent rare-disease research pipeline that reasons over a patient's genetic variants
and returns a ranked **evidence dossier** of candidate explanations, each with an explicit
uncertainty label. **Every one of the eight agents reasons on Meta's Muse models
(`muse-spark-1.3`)** — Meta is the engine, end to end. On 15 solved public benchmark cases
the Meta-powered pipeline scored **100% top-1 and 100% top-5** (every expected gene ranked
#1), across 66 real Meta completions with zero failures.

## How a facility with a VCF database connects

A facility does not hand Navigator its whole database or a standing connection. It keeps its
VCF data as the system of record and submits **one research case (one sample) at a time** to
a single authenticated endpoint. The flow:

1. **One API key per facility.** The maintainer issues it (`scripts/manage_api_keys.py issue`);
   only a salted SHA-256 hash is stored — the plaintext is never recoverable, only revocable.
   The facility sends it as the `X-API-Key` header on every call.
2. **Discover limits:** `GET /api/v1/me` returns the facility's enforced throttling limits.
3. **Submit a case:** `POST /api/v1/analyze`, either as a **VCF upload** (multipart) or as
   **parsed variants in JSON**, with optional clinical summary and HPO terms.
4. **Retrieve results:** the ranked dossier comes back in the response; the rendered PDF is
   available at `GET /api/v1/dossier/{case_id}`.

A facility with many samples writes a short loop that submits each sample as its own case,
paced by the rate limits below. Navigator never becomes the system of record for patient data.

## Data-pipeline efficiency — how we keep the payload workable for the 8 agents

This is the deliberate architectural choice we want to highlight. A real genome VCF holds
**100,000 to 5,000,000 variants** — far too many to hand to reasoning agents, and far too
expensive and non-deterministic to filter with an LLM. So **before any Meta agent sees a
single variant**, every facility submission passes through a deterministic, non-LLM
**genomic data layer** (six stages) that does the heavy reduction in cheap, auditable,
reproducible data engineering:

| Stage | What it does |
|---|---|
| 01 Ingest & Normalize | Validate header/reference build; left-align indels; split multiallelic sites; stream records (never load the whole file into RAM). |
| 02 QC & Hard Filters | Keep `FILTER=PASS`; enforce depth / genotype-quality / allele-balance thresholds. |
| 03 Columnar Store | Persist normalized variants (Parquet, partitioned by chromosome) for vectorized scans. |
| 04 Index | Region / gene / rsID lookup. |
| 05 Annotate | Join population frequency (gnomAD), clinical significance (ClinVar), and phenotype-panel membership. |
| 06 Filter & Rank (the GATE) | Score each variant on **rarity, consequence severity, phenotype match, clinical significance, and inheritance pattern**, then keep only the **top ~200 ranked candidates**. |

Only that small, ranked, fully-provenanced candidate set — **typically tens to low
hundreds of variants** — is passed to the 8 Meta agents. The reduction is **explainable**:
every surviving candidate records `{score, factors, filters_passed}`, so a researcher can
see exactly why it reached the agents and in what order.

The message for judges: **the right tool for each job.** Deterministic data engineering
handles the million-variant reduction; Meta's Muse models handle the reasoning over a
trustworthy shortlist. We never waste expensive, non-reproducible LLM calls on brute
filtering, and the Meta models never reason at raw-genome scale.

## Intake limits — so one facility can't overwhelm shared capacity

All limits are **per API key** and apply only to `/api/v1` (the public web demo is never
throttled). Defaults, raisable per facility:

| Limit | Default | On exceed |
|---|---|---|
| VCF upload size | 25 MB | 413 |
| Variants per request | 50,000 | 413 |
| Requests per minute | 10 | 429 + `Retry-After` |
| Requests per day | 200 | 429 + `Retry-After` |
| Concurrent analyses | 2 | 429 + `Retry-After` |

**Important — where the 50,000 cap is measured.** On the facility path the data-layer gate
runs **first**, so the per-request variant cap is applied to the **post-reduction candidate
set** (the ~200 variants the agents actually receive), **not** to the raw VCF record count.
A dense VCF with far more than 50,000 raw records is therefore reduced first and passes,
rather than being rejected at the door. The **25 MB upload size limit remains the raw-file
guardrail.**

## Scaling honestly to whole genomes

A true whole-genome VCF (millions of variants) is roughly **1–5 GB**, which **exceeds the
25 MB multipart upload limit** — so it is not submitted as a single direct upload today.
Real whole-genome scale is handled by **facility-side pre-reduction** (the facility runs an
equivalent normalize/QC/filter step and submits the candidate set), or by a **future
server-side / object-store transport** (the facility drops the file in storage and Navigator
streams it through the same data layer). The reasoning architecture is already built for
genome scale — the data layer reduces millions to a workable shortlist before the agents —
and the current API transport is sized for **exome-scale and pre-filtered files**. This
boundary is stated plainly rather than overclaimed.

## Does filtering block discovery of *new* disease variants? No.

A fair question about any variant-reduction gate: *if you drop variants, won't you drop the
novel disease-causing one you're trying to find?* Navigator's gate is designed so the answer
is no, because **it does not filter by "known to be harmless."** It never asks whether a
variant is on a benign blocklist. The only hard exclusion is by **population frequency**:

- **The one hard drop is "common in the general population" (allele frequency above ~1%).**
  A variant carried by many healthy people cannot be the cause of a *rare* disease, so
  removing it loses no rare-disease candidate. That is the only variant class discarded.
- **Novel / never-before-seen variants are protected, not dropped.** A brand-new variant has
  no frequency record; the gate scores that as *"frequency unknown"* with a neutral-to-
  positive weight — explicitly **never penalized for a frequency we cannot see** — and keeps
  it. A rare or absent variant with a damaging consequence (frameshift, stop-gain, splice)
  scores **high** and rises to the top of the candidate set. The novel disease variant is the
  *highest-scoring* kind of candidate, not a casualty of the filter.
- **The gate ranks; it does not pass verdicts.** A ClinVar "benign" annotation only lowers a
  score — it never hard-excludes (except the frequency rule). Variants of unknown
  significance stay in and are ranked on rarity + consequence severity + phenotype match +
  inheritance pattern. Every surviving candidate records *why* it scored where it did
  (`{score, factors, filters_passed}`), so a researcher can audit and override the ordering.

So the funnel is **"remove the common noise, keep and rank everything plausibly rare —
especially the novel."** That is the standard rare-disease discovery strategy, and it is why
reduction and discovery are not in tension here.

**Stated limits (not overclaimed):** no automated filter is perfect. A disease variant that
is relatively common, or a non-coding/regulatory variant with low predicted severity, can
score low. That is exactly why outputs are **ranked research hypotheses with uncertainty
labels for a researcher to review** — not a closed answer — and the full ranked set remains
inspectable.

## Genome storage: bring-your-own vs. Navigator-supplied

Genome-scale files (1–5 GB) are staged in object storage and streamed into the data layer a
few MB at a time, rather than sent as a single multipart upload. Each facility key carries a
**storage mode**, so Navigator meets each site at its own data-governance posture:

- **Bring-your-own bucket (BYO) — default for facilities with their own cloud/governance.**
  The facility grants Navigator scoped, time-limited access to *their* S3 bucket/prefix
  (a cross-account IAM role, or a presigned URL they generate). Navigator range-streams the
  object through the deterministic data layer and **never copies the raw genome out**.
  Encryption keys (their KMS), data residency, retention and audit logging all stay on the
  facility's side. This is the strongest privacy posture and the recommended path for
  hospitals, labs and regulated institutes.

- **Navigator-supplied storage — for pilots and small research groups.** The genome lands
  in Navigator's own encrypted bucket under a **key-scoped prefix** for that facility, with a
  lifecycle rule that **auto-deletes the raw file after reduction** to the candidate set.
  Best for sites with no cloud-ops capacity that want "just send it to us."

Both modes feed the **same streaming reducer** — only the source and credentials differ —
and in both cases Navigator's design goal is to **avoid retaining the raw genome**: it
streams, reduces to the ~200-candidate shortlist, and discards. For production, the
Navigator-supplied bucket lives in Navigator's own AWS account (encryption, retention and
access logging under its control), not the development platform's shared storage.

## Why this is a strong, responsible design

- **Meta is the engine** — all 8 agents reason on `muse-spark-1.3`; 100% top-1 on 15 solved public cases.
- **Governance is real, not aspirational** — hashed keys, per-facility throttling/quotas, revocation, size and variant guardrails — all implemented and covered by the automated test suite.
- **Responsible scope** — research-use-only framing is enforced in every response payload; Navigator does not hoard facility data and makes no diagnostic claim.

Full technical reference with copy-paste curl/Python examples: `docs/RESEARCHER_API.md`.
