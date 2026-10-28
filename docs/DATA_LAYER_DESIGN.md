# Navigator — Genomic Streaming Data Layer

**The deliberate move: a principled data substrate, not +16 more agents.**

Scaling the swarm from 8 toward ~24 agents adds coordination cost and non-determinism without
solving the real bottleneck: a real genome is 100k–5M variants, and you cannot — and should not —
hand that to LLM agents. The leverage is a deterministic data layer that reduces raw genome input
to a small, ranked, well-provenanced candidate set **before any agent sees a variant**. Heavy
reduction is cheap, auditable data engineering; agent reasoning stays lean and trustworthy.

See the one-page map: `docs/data_layer_map_1680x830.png` (source: `docs/data_layer_architecture.html`).

---

## Where the pilot is today

`src/pipeline/vcf.py` is a lightweight, dependency-free, line-by-line VCF reader:
- regex/`INFO`-string parsing for gene, HGVS and AF; `max_variants=10000` hard cap;
- no normalization (multiallelics not split, indels not left-aligned);
- no QC thresholds, no columnar store, no index, no annotation join, no deterministic rank gate.

Every parsed variant flows straight to the Intake agent. Fine for small, pre-filtered candidate
lists (the current demo cases); it does not hold up on a real WES/WGS file. This design replaces it.

---

## The layer, stage by stage

**01 · Ingest & Normalize** — `bcftools norm` + `pysam.VariantFile`
Validate header and reference build (GRCh37/38). Left-align indels, split multiallelic sites,
decompose. Stream records; never load the whole VCF into RAM.

**02 · QC & Hard Filters** — `bcftools view`
Keep `FILTER=PASS`. Enforce depth (DP), genotype quality (GQ) and allele balance. Mask
low-complexity / known-artifact regions via an optional BED.

**03 · Columnar Store** — `pyarrow` → Parquet, partitioned by chromosome
Persist normalized variants once. Vectorized scans and predicate push-down replace repeated text
re-parsing. Columns: `chrom, pos, ref, alt, gene, consequence, gnomad_af, clinvar, cadd, gt, dp, gq`.

**04 · Index** — `tabix` + lightweight maps
bgzip + tabix for region queries; `gene → variant` and `rsID → variant` maps for O(1) agent lookups.

**05 · Annotate (join)** — reference datasets, cached locally
Join population AF (gnomAD), clinical significance (ClinVar), in-silico scores (CADD) and phenotype
gene panels (HPO). Reuse the existing `data/cache/` pattern.

**06 · Filter & Rank — the GATE (deterministic)**
Rarity (gnomAD AF threshold), consequence severity, phenotype match (HPO), and inheritance model
(de novo / recessive / comp-het) when trio data is present. Emits a **ranked, provenance-logged
candidate set** of tens to low hundreds of variants.

**Output → Agent swarm** — the 8 agents reason over the curated candidate set, never millions.

---

## Why this is the right investment

- **Scale:** turns an intractable 5M-variant input into a tractable candidate set.
- **Reproducibility:** the filtering is deterministic, logged and re-runnable — exactly what the
  research-tool framing requires. Variant selection is not an LLM black box.
- **Cost & latency:** deterministic compute is orders of magnitude cheaper than LLM passes over
  raw data; the swarm stays small.
- **Auditability:** every candidate carries provenance (which filters it passed, which scores drove
  its rank), which strengthens the evidence dossier.

---

## Suggested build order (incremental, non-breaking)

1. Add `bcftools`/`pysam` ingest + normalize behind the existing `parse_vcf` interface (keep the
   current reader as a fallback for tiny inputs).
2. Add the Parquet columnar store + chrom partitioning; write once on intake.
3. Add the annotation join against the cached reference sets.
4. Add the deterministic Filter & Rank gate; have Intake consume its ranked output.
5. Add tabix + the gene/rsID indexes for agent lookups.

Each step is a drop-in that narrows what reaches the agents; none requires touching agent logic
beyond pointing Intake at the gate's output.

---

## Stage 01 — implementation notes (built)

**Status:** Stage 01 (Ingest & Normalize) is implemented and verified offline.

**Tool availability (this environment):**
- `bcftools` **1.19** (system, `/usr/bin/bcftools`) — preferred engine.
- `pysam` **0.24.1** (`/opt/abacus-python`, `pip`) — fallback engine, also handles bgzip input.
- Both are resolvable by the live `navigator` systemd service (service `PATH` includes
  `/usr/bin`; the service Python is `/opt/abacus-python`).

**Code paths added:**
- `src/pipeline/ingest.py` (new) — the deterministic, non-LLM Stage 01 module:
  - `tool_availability()` — cached capability check (`bcftools` / `pysam` versions).
  - `inspect_header()` — validates the header and detects the reference build
    (GRCh38/GRCh37, incl. `hg38`/`hg19` and `##contig ... assembly=`); unknown build is
    recorded, never fatal.
  - `normalize_to_lines()` — streams normalized VCF data lines: `bcftools norm -m-`
    (split multiallelics) with optional `-f <ref.fasta>` for left-alignment; falls back to
    `pysam.VariantFile` streaming + text-level multiallelic split; raises
    `NormalizationUnavailable` if neither tool is present.
  - Header-light demo/snippet VCFs are handled by streaming them through a temp copy with
    missing standard `##contig` lines injected (constant memory), so strict `bcftools`
    does not reject records.
- `src/pipeline/vcf.py` (extended, **non-breaking**) — `parse_vcf` / `iter_variants` now
  take optional `normalize=True` and `ref_fasta=None`. When a tool is available the
  normalized path runs; on any failure (or no tool) it transparently falls back to the
  original dependency-free line reader. A shared `_variant_from_cols()` guarantees a given
  record yields an identical `Variant` on either path. **`src/agents/intake.py` was not
  changed** — it still calls `parse_vcf(p)` and now gets normalization for free.
- `tests/test_ingest.py` (new, offline) — 11 tests: GRCh38/GRCh37 build detection,
  unknown-build-not-fatal, multiallelic split (bcftools and pysam-only paths), `.vcf.gz`
  streaming, graceful fallback when tools are simulated absent, per-allele `AF` subsetting,
  and proof the bundled demo VCF parses identically via the normalized path.

**Verification:** `tests/test_ingest.py` 11/11 pass; full suite 22/22 pass (no regression).
Live service restarted and healthy (HTTP 200); the demo VCF (`samples/sample_unknown.vcf`)
parses and runs through the Intake agent via the normalized path.

**Known limitations (honest scope):**
- **Left-alignment requires a reference FASTA.** None is bundled, so for the demo inputs
  Stage 01 currently performs *split-multiallelics / decompose only* and logs that
  left-align was skipped. Supplying `ref_fasta=` (a matching GRCh37/38 FASTA) enables full
  left-alignment via `bcftools norm -f`.
- The pysam fallback splits multiallelics at the text level (preserving values exactly) but
  does not left-align even with a FASTA — use `bcftools` for left-alignment.
- Stages 02–06 (QC filters, Parquet columnar store, tabix index, annotation join, the
  deterministic rank gate) are **not** built yet; this delivers Stage 01 only.

---

*Research use only — not a diagnostic system, not medical advice.*
