# Navigator Genome Pilot — Hackathon Submission Write-up

**Meta Global AI Developer Hackathon · Indie Developer track**
_Copy-paste-ready. Each section is labeled with the submission-form field it answers. Fill the
bracketed `[...]` items (video URL) before you submit._

---

## Field: Project name
Navigator Genome Pilot

## Field: Tagline (one line)
An agentic research tool that reads a genome variant list and a patient's clinical picture, then assembles a sourced, uncertainty-labeled evidence dossier for rare-disease researchers — eight specialized agents, every claim cited, built to say when it doesn't know.

## Field: Links
- **Live demo:** https://navigator-genome.abacusai.cloud
- **Public repository:** https://github.com/troy214/navigator-genome-pilot
- **3-minute demo video:** https://youtu.be/PlMU0qrLrPY  _("NAVIGATOR PILOT / META MUSE", public on YouTube. Mirror/direct file: https://navigator-genome.abacusai.cloud/demo.mp4)_

## Field: Track / Theme
Indie Developer track. Theme fit: **Build for Your World / Push the Frontier** — an agentic research-acceleration platform for rare-disease variant interpretation.

> **Research use only — not a diagnostic system.** Navigator interprets genome variants and
> assembles evidence dossiers for researchers and clinicians. It is **not a diagnostic system
> and does not give medical advice** to any patient or end user. It is evaluated only on
> already-solved, published public cases with the answer hidden — it measures a research
> protocol, not advice to a person. Every output carries explicit uncertainty labels and is
> decision *support* for an expert, never a diagnosis.

---

## Field: What it does (full description)

Diagnosing a rare genetic disease means taking a list of candidate DNA variants and a messy
clinical picture, then cross-checking them against genetics databases, population-frequency
data, phenotype ontologies, and the published literature — and then arguing with yourself about
what the evidence actually supports. For a single case that is days of expert work across a
dozen tools.

Navigator Genome Pilot runs that investigation as **eight specialized AI agents**, each working
in its own isolated context, coordinated into a single sourced **evidence dossier**:

1. **Intake** — parses the VCF / structured case and normalizes the candidate variants.
2. **Filtering** — reduces candidates by population frequency and quality, and *explains every
   exclusion* (e.g. drops a common variant because its allele frequency is too high for a rare
   disease).
3. **Phenotype (HPO)** — maps the free-text clinical picture to standardized Human Phenotype
   Ontology terms via the live HPO / JAX ontology API.
4. **Literature** — searches Europe PMC; every claim it returns carries a real PMID/DOI.
5. **Database** — queries MyVariant.info, ClinVar (NCBI), and gnomAD (GraphQL) live.
6. **Case-Matching** — compares the case against a library of known solved cases with a
   similarity rationale.
7. **Red Team** — runs in a deliberately isolated context that never sees a leading hypothesis,
   and argues *against* the emerging conclusion to surface weaknesses.
8. **Dossier Writer** — assembles a ranked, physician-facing dossier and renders it to PDF with
   a research-use-only footer.

The output is not a verdict. It is a **ranked, cited, uncertainty-labeled dossier**: top
candidate gene/variant, the supporting evidence with sources, the *contradicting* evidence, and
an explicit statement of what remains unknown.

**The defining principle — knowledge discipline.** Every row in the evidence ledger is tagged
as **Idea / Designed / Implemented / Verified**, or explicitly **Unknown**. When ClinVar has no
record for a variant, Navigator labels it *absent — not benign*. When an external API is down,
the dossier says so rather than guessing. The system is built to **say when it doesn't know** —
which is exactly what makes a research tool trustworthy to an expert.

## Field: The bigger platform (verticals)

The rare-disease pilot you see today is **one laboratory** running on a general architecture.
Navigator is not fundamentally a "genome hunter" — it solves a repeating pattern: **too much raw
evidence, too little time, and a decision that must be explainable.** Every Navigator laboratory
runs the same four-part spine — a deterministic data-reduction layer, a swarm of isolated
Meta-Muse expert agents, an adversarial red-team agent, and a dossier writer — and produces the
same kind of output: a **ranked, sourced, uncertainty-labeled evidence dossier**. Only the data
sources, expert panels, and ranking heuristics change between verticals.

The eight pilot agents are generic reasoning roles pointed at genomic data: ingest & normalize,
deterministic reduce, map-to-vocabulary, search the literature, query authoritative sources,
retrieve precedent, adversarial review, and assemble the dossier. Swap the sources, keep the
spine, and you have a new laboratory:

- **Genome Navigator** — *live and benchmarked today* (research use only, not a diagnosis).
- **Media Navigator** — reduce a flood of articles/transcripts/clips to the claims that matter;
  sourced briefings for newsrooms and analysts.
- **Government Navigator** — reduce statutes, filings, and dockets to relevant provisions and
  precedents; cited policy dossiers.
- **Research Navigator** — reduce a literature corpus to the findings bearing on a hypothesis;
  review-grade dossiers.
- **Corporate Intelligence Navigator** — reduce filings/news/market signals to decision-ready
  briefs.
- **Patent Navigator** — reduce a prior-art space to the references most relevant to a claim;
  prior-art / FTO dossiers.

**One honest boundary:** only the Genome laboratory is live and benchmarked today. The other four
are architecturally ready — they reuse the same proven spine — but are presented as the **platform
roadmap**, not shipped products. Every laboratory's reasoning runs on Meta Muse, so more verticals
mean more Meta-powered reasoning on the same proven engine. Full write-up:
`docs/NAVIGATOR_PLATFORM_VISION.md`.

## Field: How we use Meta's models

All **eight runtime agents reason on Meta's `muse-spark-1.3`** through the Meta Model API
(`https://api.meta.ai/v1`) — the model name verified live against Meta's model catalog and set
for every agent in `config/agents.yaml`. This is **not aspirational**: the full 15-case
benchmark was executed on the live Meta Model API, logging **66 real Meta completions (66/66
succeeded, 0 failed)** and **155,168 API-reported tokens**, and scoring **top-1 = 100% /
top-5 = 100%**. The machine-readable proof is in `benchmarks/results/scores_meta.json`
(`"valid_meta_run": true`, proof gate passed) and `benchmarks/results/report_meta.md`.

The whole pipeline goes through one OpenAI-compatible model client, so no agent code hard-codes a
model name — the provider is chosen by environment, and swapping the dev proving-ground for the
live Meta Model API is a single environment variable (`META_MODEL_API_KEY`; checklist in
`docs/TRANSPOSE_TO_META.md`). Muse Code is used to help *build* the platform, not as a runtime
agent.

_Open-weight bonus:_ Meta's catalog exposes `-contributor` variants of Muse Spark. We have a
designed (not yet verified) path to route the three highest-volume agents (intake, filtering,
database) to `muse-spark-1.3-contributor` — a YAML-only change — to pursue the *Best Build on
Meta Open-Weight Models* bonus. We present that as a roadmap item rather than claiming it today.

## Field: Tech stack / Architecture

- **Agents (reasoning engine):** Meta's `muse-spark-1.3` via the Meta Model API — one isolated
  context per agent; the full benchmark has been run live on this path (66/66 real completions).
- **Provider switch:** the same pipeline also runs on an OpenAI-compatible dev endpoint for
  offline development, selected by a single environment variable — no agent code changes.
- **Infrastructure backbone:** **AWS** — orchestration, the demo app, and dossier storage (S3).
- **Live, keyless public data sources:** Europe PMC, MyVariant.info, ClinVar (NCBI), gnomAD,
  HPO / JAX ontology.
- **App:** FastAPI backend + a vanilla-JavaScript single-page UI (agent board, evidence ledger,
  dossier view, one-click PDF download).
- **Backend:** Python; streaming VCF parser; disk-cached, rate-limited HTTP clients; reportlab
  PDF rendering; a benchmark harness that scores top-1 / top-5 against hidden answers.

## Field: What we built / current status (honest)

**Verified** — actually executed, with artifacts in the repo:

- All **8 agents** run end-to-end through the coordinator, with per-run persistence.
- **Meta Model API inference is live and proven** — the benchmark ran on `muse-spark-1.3` via
  `https://api.meta.ai/v1` with **66/66 real Meta completions** (proof gate passed,
  `benchmarks/results/scores_meta.json`).
- **Benchmark: top-1 = 100%, top-5 = 100%** over **15** published, already-solved cases
  (CF/CFTR, DMD, FH/LDLR, HBOC/BRCA1, HD/HTT, HEMA/F8, MFS/FBN1, PKU/PAH, POMPE/GAA,
  RETT/MECP2, SCD/HBB, SMA/SMN1, TSD/HEXA, VHL, Wilson/ATP7B) with answers hidden —
  every expected gene ranked #1.
- **Live** calls to Europe PMC, MyVariant, ClinVar, gnomAD, and HPO — real sources, no keys.
- Real **PDF dossiers** generated for solved cases.
- **77 offline tests pass** (LLM + HTTP mocked), including the red-team isolation check, the
  absent-vs-benign rule, and the facility data-layer gate / intake-cap controls.
- **Live, public demo** and a **public GitHub repository**.

**Designed, not yet Verified** — honestly labeled in `docs/STATUS.md`:
- **AWS deployment + S3 dossier storage** — documented as the backbone; the live demo currently
  runs on a development VM, with the S3 upload destination computed and ready to wire.
- **Open-weight routing** to `muse-spark-1.3-contributor` for the three highest-volume agents — a
  YAML-only change, not yet executed.

We do not mark anything "Verified" that we have not actually executed — that discipline is the
point of the project.

## Field: Inspiration

Rare-disease families often spend years on a "diagnostic odyssey." The bottleneck is rarely the
sequencing — it is the human-scale work of interpreting variants against a sprawl of databases
and literature. We wanted to see whether an agentic system could *accelerate the research
protocol* — not replace the clinician, but assemble the sourced, self-skeptical dossier that a
researcher would otherwise spend days building by hand.

## Field: Challenges we ran into

- **Keeping it honestly a research tool.** The hard discipline was building something genuinely
  useful while never crossing into giving medical advice — hence benchmarking only on solved
  public cases, uncertainty labels on every claim, and the research-use notice everywhere.
- **Making agents skeptical, not confident.** The Red Team agent runs in an isolated context so
  it can't be anchored by the pipeline's leading hypothesis.
- **Absent ≠ benign.** A missing database record is a genuine unknown, not reassurance; encoding
  that correctly took deliberate design.
- **Proving the logic before paid access.** We built a provider switch so the entire pipeline is
  provable on a dev endpoint today and flips to Meta's models with one environment variable.

## Field: What's next

- Deploy the backbone on AWS (ECS/Fargate) and wire the S3 dossier-storage path end-to-end
  (facility-owned encrypted buckets for governed facilities; Navigator-supplied storage for demos
  and pilots) — the integration design is in `docs/META_FACILITY_INTEGRATION.md`.
- Route the three highest-volume agents to `muse-spark-1.3-contributor` (open-weight) and verify
  the benchmark holds, to pursue the open-weight bonus.
- Grow the benchmark beyond the current 15 solved public cases across more genes and disease types.
- Light up the next laboratory on the same spine (Media or Research Navigator) to demonstrate the
  cross-vertical platform, not just the genome pilot.
- Add the roadmap agents: translator agents that search foreign-language literature by gene +
  HGVS variant name, and a regional-focus tool for founder-population studies.

## Field: Team
Troy Burns (solo / Indie Developer track).

---

### Short version (if the form has a tight character limit)

Navigator Genome Pilot is an agentic **research tool** for rare-disease variant interpretation.
Eight specialized Meta-model agents — intake, filtering, HPO phenotyping, literature (Europe
PMC), databases (ClinVar/gnomAD/MyVariant), case-matching, an isolated red-team, and a dossier
writer — investigate a genome variant list and clinical picture, then assemble a ranked, **fully
sourced, uncertainty-labeled evidence dossier** (PDF). Every claim is tagged
Idea/Designed/Implemented/Verified or explicitly Unknown; absent database records are labeled
*absent, not benign*; the system says when a source is down. It is **not a diagnostic system and
gives no medical advice** — it is benchmarked only on already-solved public cases with the
answer hidden (**top-1 100% / top-5 100%** on 15 cases, 66/66 real Meta completions). All eight
agents reason on Meta's **`muse-spark-1.3`** via the Meta Model API; **AWS** is the backbone. Live:
https://navigator-genome.abacusai.cloud · Repo:
https://github.com/troy214/navigator-genome-pilot
