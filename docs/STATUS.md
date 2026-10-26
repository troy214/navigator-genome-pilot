# Status — knowledge-category tracker

Tracked with the same four categories Navigator enforces (Idea / Designed / Implemented /
Verified), plus explicit Unknown. "Verified" means it was actually run successfully in this
environment on the dev provider — NOT that it is validated against the production Meta models.

_Last updated: Oct 26, 2026 (pilot build on dev endpoint)._

| Component | Category | Evidence |
|-----------|----------|----------|
| Repo structure | Implemented | — |
| Provider switch (dev ↔ Meta, env-only) | **Verified** | runs on dev endpoint; Meta path is code-complete but **Designed** (no live Meta key tested) |
| Model client (timeouts/retries/JSON mode) | **Verified** | live calls to `gpt-5.4-mini` succeed with JSON mode + graceful fallback |
| VCF intake (streaming parser) | **Verified** | parses bundled `cystic_fibrosis.vcf` (2 variants, gene/HGVS/AF); unit-tested |
| Agent 1 Intake | **Verified** | normalizes VCF + structured variants end-to-end |
| Agent 2 Filtering | **Verified** | excludes common variants (MUC5B AF 0.12) with explanation |
| Agent 3 Phenotype (HPO) | **Verified** | maps clinical text → real HP: IDs via JAX ontology API |
| Agent 4 Literature | **Verified** | Europe PMC search; every claim carries a real PMID/DOI |
| Agent 5 Database | **Verified** | live MyVariant.info + ClinVar + gnomAD; absent≠benign enforced |
| Agent 6 Case-Matching | **Verified** | similarity over bundled solved-case library |
| Agent 7 Red Team | **Verified** | isolated context (unit-tested: no leading hypothesis), raises critiques |
| Agent 8 Dossier Writer | **Verified** | renders 4-page PDF with findings, ledger, uncertainty, research-use footer |
| Coordinator pipeline | **Verified** | end-to-end run on 3 real cases; per-run logs persisted to `data/runs/` |
| Benchmark scoring | **Verified** | top-1=100%, top-5=100% over 3 solved cases (`benchmarks/results/`) |
| Demo web app | **Verified** | agent board + evidence ledger + dossier view; run + PDF download work |
| Public hosting | **Verified** | live at https://navigator-genome.abacusai.cloud (nginx + systemd), crawl-verified |
| Offline test suite | **Verified** | 11 tests pass with LLM + HTTP mocked (`pytest`) |
| Meta Model API (production) | **Designed** | one-env-var swap; NOT yet run against a live Meta key |
| AWS deployment (prod backbone) | **Designed** | documented in `infra/aws/`; dev demo runs on this VM, not AWS yet |
| S3 dossier storage | **Designed** | destination computed + documented; upload code is a TODO pending bucket |

**Rule:** do not advance a row's category without the evidence in the right column. The two
remaining production rows (Meta inference, AWS deployment) stay **Designed** until Troy runs
them in the Meta/AWS environment — this is the honest line between "proven on dev" and
"proven in production."
