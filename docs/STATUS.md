# Status — knowledge-category tracker

Tracked with the same four categories Navigator enforces (Idea / Designed / Implemented /
Verified), plus explicit Unknown. "Verified" means it was actually run successfully in this
environment on the dev provider — NOT that it is validated against the production Meta models.

_Last updated: Oct 27, 2026 (billing resolved; live demo now runs on the Meta Model API — `muse-spark-1.3`; benchmark re-run on Meta: top-1=100%, top-5=100% over 3 solved cases)._

| Component | Category | Evidence |
|-----------|----------|----------|
| Repo structure | Implemented | — |
| Provider switch (dev ↔ Meta, env-only) | **Verified** | live service switched to `PROVIDER=meta` end-to-end; `scripts/activate_meta.sh` flips it and health-checks |
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
| Public GitHub repo (hackathon req) | **Verified** | published public at https://github.com/troy214/navigator-genome-pilot (main, 9 commits, 67 files, no secrets) |
| Offline test suite | **Verified** | 11 tests pass with LLM + HTTP mocked (`pytest`) |
| Meta Model API — key + catalog | **Verified** | Troy's key authenticates to `https://api.meta.ai/v1`; `GET /models` returns the live catalog; real model id is `muse-spark-1.3` (placeholders `muse-spark`/`muse-spark-open-1026` were wrong and are now corrected in `config/agents.yaml`) |
| Meta Model API — live inference | **Verified** | billing resolved; live service runs `PROVIDER=meta` on `muse-spark-1.3`. Real chat completions succeed; `/lab-data` serves 8 agents on Meta. |
| Benchmark on Meta models | **Verified** | re-run 2026-10-27 on Meta: top-1=100%, top-5=100% over 3 solved cases (CF/CFTR, PKU/PAH, SCD/HBB); `benchmarks/results/scores.json` shows `provider: meta` per case. |
| AWS deployment (prod backbone) | **Designed** | documented in `infra/aws/`; dev demo runs on this VM, not AWS yet |
| S3 dossier storage | **Designed** | destination computed + documented; upload code is a TODO pending bucket |

**Rule:** do not advance a row's category without the evidence in the right column. The two
remaining production rows (Meta inference, AWS deployment) stay **Designed** until Troy runs
them in the Meta/AWS environment — this is the honest line between "proven on dev" and
"proven in production."
