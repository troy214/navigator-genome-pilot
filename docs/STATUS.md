# Status — knowledge-category tracker

Tracked with the same four categories Navigator enforces (Idea / Designed / Implemented /
Verified), plus explicit Unknown. "Verified" means it was actually run successfully in this
environment on the dev provider — NOT that it is validated against the production Meta models.

_Last updated: Nov 3, 2026 (**open-weight routing verified**: intake/filtering/database now run on Meta open-weight `muse-spark-1.3-contributor`, five agents stay on `muse-spark-1.3`; full 15-case benchmark re-run under this mixed routing on the Meta Model API: **63/63 real completions, top-1=100% (15/15), top-5=100% (15/15)**). Prior: Oct 27, 2026 (billing resolved; benchmark expanded 3 → 15 cases, re-run on Meta)._

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
| Benchmark scoring | **Verified** | top-1=100%, top-5=100% over **15** solved public cases (`benchmarks/results/scores.json`) |
| Demo web app | **Verified** | agent board + evidence ledger + dossier view; run + PDF download work |
| Public hosting | **Verified** | live at https://navigator-genome.abacusai.cloud (nginx + systemd), crawl-verified |
| Public GitHub repo (hackathon req) | **Verified** | published public at https://github.com/troy214/navigator-genome-pilot (main, 9 commits, 67 files, no secrets) |
| Offline test suite | **Verified** | 77 tests pass with LLM + HTTP mocked (`pytest`) |
| Meta Model API — key + catalog | **Verified** | Troy's key authenticates to `https://api.meta.ai/v1`; `GET /models` returns the live catalog; real model id is `muse-spark-1.3` (placeholders `muse-spark`/`muse-spark-open-1026` were wrong and are now corrected in `config/agents.yaml`) |
| Meta Model API — live inference | **Verified** | billing resolved; live service runs `PROVIDER=meta` on `muse-spark-1.3`. Real chat completions succeed; `/lab-data` serves 8 agents on Meta. |
| Benchmark on Meta models | **Verified** | **expanded to 15 solved public cases and re-run 2026-10-27 on Meta (`muse-spark-1.3`): top-1=100% (15/15), top-5=100% (15/15)**; `benchmarks/results/scores.json` shows `provider: meta` for every case, and a persisted run (`data/runs/WILSON-ATP7B-H1069Q_*`) records `provider: meta`. See case list below. |
| Open-weight routing (bonus) | **Verified** | intake/filtering/database routed to open-weight `muse-spark-1.3-contributor` (config/agents.yaml); full 15-case benchmark re-run 2026-11-03 under this routing: 63/63 real Meta completions, top-1=100%, top-5=100% (`benchmarks/results/scores_meta.json`, `report_meta.md`) |
| AWS deployment (prod backbone) | **Designed** | documented in `infra/aws/`; dev demo runs on this VM, not AWS yet |
| S3 dossier storage | **Designed** | destination computed + documented; upload code is a TODO pending bucket |

**Rule:** do not advance a row's category without the evidence in the right column. The two
remaining production rows (Meta inference, AWS deployment) stay **Designed** until Troy runs
them in the Meta/AWS environment — this is the honest line between "proven on dev" and
"proven in production."



---

## Benchmark case set — 15 solved public cases (Verified on Meta)

All cases are **already-solved, published, public** monogenic rare diseases — textbook
clinical presentations (HPO-mappable), **not real patients**. Each case gives the agents a
clinical picture plus a VCF-style variant set (the real rare causal variant mixed with a
common benign distractor); the causal gene/variant is held in `benchmarks/cases/_answers.json`,
**hidden from the agents** and used only by the scorer.

Run: `benchmarks/results/scores.json`, generated `2026-10-27T21:12:05Z`, **provider `meta`
(`muse-spark-1.3`) on every case**. Measured: **top-1 = 100% (15/15), top-5 = 100% (15/15)**.
Mutation types span missense, nonsense, small indels/duplications, a trinucleotide repeat
expansion, a splice variant, and a gene deletion; inheritance spans AR, AD, XLR and XLD.

| # | Case ID | Disease | Gene | Canonical variant | Mutation type | Top-1 (Meta) |
|---|---------|---------|------|-------------------|---------------|:---:|
| 1 | CF-CFTR-F508del | Cystic fibrosis | CFTR | p.Phe508del (c.1521_1523delCTT) | in-frame deletion | ✓ |
| 2 | SCD-HBB-E6V | Sickle cell disease | HBB | p.Glu6Val (c.20A>T) | missense | ✓ |
| 3 | PKU-PAH | Phenylketonuria | PAH | c.1222C>T (p.Arg408Trp) | missense | ✓ |
| 4 | DMD-DMD-R1577X | Duchenne muscular dystrophy | DMD | c.4729C>T (p.Arg1577Ter) | nonsense (XLR) | ✓ |
| 5 | HEMA-F8-R2016W | Hemophilia A | F8 | c.6046C>T (p.Arg2016Trp) | missense (XLR) | ✓ |
| 6 | TSD-HEXA-1278insTATC | Tay-Sachs disease | HEXA | c.1274_1277dupTATC (p.Tyr427IlefsTer5) | frameshift insertion | ✓ |
| 7 | SMA-SMN1-EX7DEL | Spinal muscular atrophy type 1 | SMN1 | homozygous exon-7 loss (c.840C>T) | deletion/gene conversion | ✓ |
| 8 | MFS-FBN1-C1170Y | Marfan syndrome | FBN1 | c.3509G>A (p.Cys1170Tyr) | missense (AD) | ✓ |
| 9 | FH-LDLR-G592E | Familial hypercholesterolemia | LDLR | c.1775G>A (p.Gly592Glu) | missense (AD) | ✓ |
| 10 | RETT-MECP2-T158M | Rett syndrome | MECP2 | c.473C>T (p.Thr158Met) | missense hotspot (XLD) | ✓ |
| 11 | HD-HTT-CAG-EXP | Huntington disease | HTT | expanded CAG repeat (~42) exon 1 | repeat expansion (AD) | ✓ |
| 12 | POMPE-GAA-IVS1 | Pompe disease (late-onset) | GAA | c.-32-13T>G | splice (AR) | ✓ |
| 13 | WILSON-ATP7B-H1069Q | Wilson disease | ATP7B | c.3207C>A (p.His1069Gln) | missense (AR) | ✓ |
| 14 | HBOC-BRCA1-185delAG | Hereditary breast/ovarian cancer | BRCA1 | c.68_69delAG (185delAG) | frameshift deletion (AD) | ✓ |
| 15 | VHL-VHL-R167W | Von Hippel-Lindau disease | VHL | c.499C>T (p.Arg167Trp) | missense (AD) | ✓ |

**Excluded cases:** none — all 15 authored cases ran end-to-end on Meta and scored.

**Honest scope of this result (Verified vs Unknown):**
- **Verified:** on these 15 published, already-solved cases the pipeline ranked the correct
  causal gene first on `muse-spark-1.3`. This measures the system's ability to re-derive
  *known* answers from a clinical picture + variant list, with real evidence pulled live from
  Europe PMC / MyVariant / ClinVar / gnomAD / HPO.
- **Unknown (not claimed):** performance on *unsolved* or novel cases, on harder
  needle-in-a-haystack variant sets (dozens–hundreds of candidates per case), on
  non-monogenic/complex disease, and inter-run variance at scale. These are out of scope for
  this benchmark and remain Unknown. Navigator stays a **research tool** — it outputs ranked
  hypotheses with explicit uncertainty, not diagnoses.
