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
- Supersedes the earlier note: Stages 02–06 are now built (see below).

---

## Stages 02–06 — implementation notes (built)

**Status:** Stages 02 (QC & hard filters), 03 (columnar store), 04 (index), 05 (annotate),
and 06 (filter & rank — the gate) are implemented and verified offline, plus an
orchestration entry point that chains 01→06. All stages are deterministic, non-LLM, and
**non-breaking** — `parse_vcf`/`iter_variants` and all 8 agents keep working unchanged, and
the full gated path is opt-in (default OFF).

**Tool / library versions (this environment):**
- `pyarrow` **26.0.0** — installed via `pip` into `/opt/abacus-python` (was missing).
- `pysam` **0.24.1** (`/opt/abacus-python`) — bgzip + tabix via its bundled htslib (no
  standalone `bgzip`/`tabix` binaries are required/present on PATH).
- `bcftools` **1.19** (system) — used only by Stage 01 upstream.

**Modules added (all under `src/pipeline/`, each with research-use-only docstrings):**
- `qc.py` — **Stage 02.** Streaming, line-by-line hard filter over Stage 01's normalized
  lines. Enforces `FILTER==PASS` (`.`/empty treated as "no filtering applied" = acceptable),
  and configurable `DP`/`GQ`/allele-balance thresholds (`QCThresholds`; defaults permissive
  = PASS-only so the demo is unchanged, `QCThresholds.recommended()` = DP≥10/GQ≥20/AB 0.2–0.8).
  Optional BED region mask (`BedMask`, 0-based half-open vs VCF 1-based, chr-prefix tolerant).
  **Missing-field policy (deliberate):** a quality field that is *absent* (e.g. demo VCFs with
  no FORMAT/sample columns) **passes** its check — we never drop a variant for a metric we
  cannot see; only a present-and-failing field drops it. Provenance via `QCStats`.
- `store.py` — **Stage 03.** Writes QC'd variants ONCE to Parquet via pyarrow, **partitioned
  by chromosome** (`<store>/<case_id>/chrom=<chrom>/…`). Columns (nulls where unknown):
  `chrom,pos,ref,alt,gene,consequence,gnomad_af,clinvar,cadd,gt,dp,gq` plus extras
  `rsid,hgvs,impact,filter`. Reader (`read_variants` / `read_variants_as_objects`) supports
  **column projection and predicate push-down** (by `chrom` partition and `max_gnomad_af`).
  Location configurable (`base_dir=` / `DATA_LAYER_STORE_DIR`; default `data/variant_store/`).
  Degrades: raises `StoreUnavailable` if pyarrow is absent and the orchestrator skips it.
- `index.py` — **Stage 04.** (1) `bgzip_and_tabix()` builds a bgzipped + tabix-indexed
  normalized VCF (via pysam's htslib) and `region_query(chrom,start,end)` does O(log n)
  region lookups (1-based inclusive, chr-prefix tolerant). (2) In-memory + JSON-persisted
  `gene → [row indices]` and `rsID → row index` maps for O(1) agent lookups. Tabix degrades
  (`IndexUnavailable`) if pysam is absent; the pure-Python maps always work.
- `annotate.py` — **Stage 05.** Deterministic join enriching each variant's `raw` with
  population AF, clinical significance, in-silico score, and phenotype-panel membership,
  using ONLY the existing cache-backed clients (no bulk downloads). Sources are injectable
  (`AnnotationSources`) so tests run fully offline; every call is wrapped and **degrades to a
  null column + `sources_unavailable` note, never raising**.
- `rank.py` — **Stage 06, the GATE.** Deterministic scoring/ranking by **rarity** (gnomAD AF
  vs `max_af`, default 0.01; missing AF scored neutrally, never penalized), **consequence
  severity** (HIGH/LoF > MODERATE/missense > LOW/synonymous, from impact+consequence),
  **phenotype match** (gene in the case panel), **clinical significance** (ClinVar
  pathogenic↑ / benign↓), and **inheritance model** (compound-het = ≥2 hets in one gene,
  homozygous-recessive; de-novo activates only with trio/parental genotypes — absent in demo
  inputs, so it degrades to no-op). Returns a new best-first list; every candidate carries
  `raw["rank"] = {score, factors, filters_passed}` for full provenance. `RankConfig` exposes
  all weights/thresholds and an optional `drop_common` / `max_candidates`.
- `data_layer.py` — **orchestration.** `run(case, config)` chains 01→06 and is independently
  callable (works with a `vcf_path` or with structured `variants`). `DataLayerConfig` carries
  all stage settings; `DataLayerResult` returns the ranked set + QC/annotation stats + artifact
  paths (store, tabix gz, lookup maps). Optional stages degrade and never hard-crash a run.

**Wired vs stubbed (honest):**
- **WIRED** — gnomAD AF and ClinVar significance via `src.clients.myvariant` (aggregates
  ClinVar/gnomAD/dbNSFP) with `src.clients.clinvar` (NCBI E-utilities) as fallback; both are
  gene-scoped, cache-backed, free-API lookups — never bulk downloads.
- **RESERVED (effectively null)** — CADD / in-silico score: the Parquet column exists and is
  filled only if a source hands one over; the minimal MyVariant client does not currently
  surface a per-variant CADD and we do **not** fetch CADD in bulk, so in practice it stays null.
- **STUBBED** — the phenotype gene panel: no offline HPO→gene panel is bundled, so
  `phenotype_match` is computed against a caller-supplied set of gene symbols
  (`phenotype_panel=`). Passing `None` skips it.
- Offline behavior: with the network stubbed (as in tests), annotation leaves AF/ClinVar null
  and records the sources as unavailable; QC/store/index/rank are fully local and unaffected.

**How to enable the full gated path (opt-in; default behavior & demo unchanged):**
- Set env `DATA_LAYER_GATE_ENABLED=1` (also `true`/`yes`/`on`). Optionally
  `DATA_LAYER_STORE_DIR=/path` to relocate the Parquet store.
- The single integration hook is `src.pipeline.data_layer.maybe_gate(case)`: when the flag is
  OFF it returns the case **untouched**; when ON it runs the layer and returns a NEW
  `CaseInput` whose `variants` are the ranked candidate set and whose `vcf_path` is cleared —
  so the Intake agent (and the rest of the swarm) consume pre-filtered, ranked variants
  through the **existing interface with zero agent code changes**. No agent currently calls
  `maybe_gate`, so default runs are byte-for-byte unchanged; wiring it in is a one-line change
  at the case-entry point when desired.

**Verification:** `tests/test_data_layer.py` 18/18 pass (QC threshold + missing-field
pass-through + BED mask; Parquet round-trip + chrom partitioning + predicate push-down; tabix
region query + gene/rsID maps; annotation join with stubbed clients + offline degradation;
rank-gate ordering — a rare high-consequence phenotype-matching variant outranks a common
benign one — + compound-het + provenance; orchestration chain + opt-in gate). Full suite
**40/40** pass (22 prior + 18 new, no regression). Live `navigator` service restarted and
healthy (HTTP 200); the demo VCF still parses and runs through Intake unchanged on the default
(non-gated) path. No `/run-new` LLM pipeline was triggered (no Meta credits spent).

**Known limitations (honest scope):**
- Demo/snippet VCFs carry no FORMAT/sample columns, so DP/GQ/AB thresholds and inheritance
  (het/hom/comp-het) are effectively inert on them by design (missing-field pass-through);
  they engage on real, fully-populated VCFs.
- De-novo detection needs trio/parental genotypes, which the current inputs lack.
- CADD/in-silico enrichment is reserved, not wired (see wired-vs-stubbed above).
- Phenotype matching depends on a caller-supplied gene panel (no bundled HPO→gene source).

---

*Research use only — not a diagnostic system, not medical advice.*
