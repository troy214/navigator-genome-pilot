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

*Research use only — not a diagnostic system, not medical advice.*
