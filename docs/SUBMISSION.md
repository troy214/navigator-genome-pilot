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

## Field: How we use Meta's models

Every runtime agent is designed to run on **Meta's models** through the Meta Model API. The
agent→model allocation (in `config/agents.yaml`) deliberately puts the three highest-volume
agents on the **open-weight** model to control cost and to qualify for the *Best Build on Meta
Open Weight Models* bonus:

| Agent | Meta model |
|-------|-----------|
| Intake, Filtering, Database | `muse-spark-open-1026` (open weight) |
| Phenotype, Literature, Case-Matching, Red Team, Dossier Writer | `muse-spark` |

The whole pipeline goes through one OpenAI-compatible model client, so no agent code mentions a
model name — the provider is chosen by environment. **Transposing from the dev proving-ground to
the live Meta Model API is a single environment variable** (`META_MODEL_API_KEY`); the full
checklist is in `docs/TRANSPOSE_TO_META.md`. Muse Code is used to help *build* the platform, not
as a runtime agent.

## Field: Tech stack / Architecture

- **Agents (production):** Meta models via the Meta Model API + partner inference (Modal /
  Baseten) — one isolated context per agent.
- **Agents (dev proving-ground, now):** an OpenAI-compatible dev endpoint, used to prove the
  full pipeline logic end-to-end before the Meta key is live.
- **Infrastructure backbone:** **AWS** — orchestration, the demo app, and dossier storage (S3).
- **Live, keyless public data sources:** Europe PMC, MyVariant.info, ClinVar (NCBI), gnomAD,
  HPO / JAX ontology.
- **App:** FastAPI backend + a vanilla-JavaScript single-page UI (agent board, evidence ledger,
  dossier view, one-click PDF download).
- **Backend:** Python; streaming VCF parser; disk-cached, rate-limited HTTP clients; reportlab
  PDF rendering; a benchmark harness that scores top-1 / top-5 against hidden answers.

## Field: What we built / current status (honest)

Everything that can be proven without a live Meta key or a paid cloud account is **built and
verified on the dev endpoint**:

- All **8 agents** run end-to-end through the coordinator, with per-run persistence.
- **Live** calls to Europe PMC, MyVariant, ClinVar, gnomAD, and HPO — real sources, no keys.
- Real **PDF dossiers** generated for three solved cases.
- **Benchmark: top-1 = 100%, top-5 = 100%** over **15** published, already-solved cases
  (CF/CFTR, DMD, FH/LDLR, HBOC/BRCA1, HD/HTT, HEMA/F8, MFS/FBN1, PKU/PAH, POMPE/GAA,
  RETT/MECP2, SCD/HBB, SMA/SMN1, TSD/HEXA, VHL, Wilson/ATP7B) with answers hidden —
  every expected gene ranked #1, across 66 real Meta Muse completions with zero failures.
- **77 offline tests pass** (LLM + HTTP mocked), including the red-team isolation check and the
  absent-vs-benign rule.
- **Live, public demo** and a **public GitHub repository**.

Two production items are honestly labeled **Designed, not Verified** in `docs/STATUS.md` because
they require credentials we have not yet exercised:
- **Meta Model API inference** — code-complete; a one-env-var swap; not yet run against a live
  Meta key.
- **AWS deployment + S3 dossier storage** — documented as the backbone; the demo currently runs
  on a development VM, with the S3 upload destination computed and ready to wire.

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

- Flip `META_MODEL_API_KEY` on, re-run the benchmark on Meta's Muse Spark models, and report the
  Meta-verified scores.
- Deploy the backbone on AWS (ECS/Fargate) with S3 dossier storage.
- Grow the benchmark from 3 to 10–20 solved public cases across more genes and disease types.
- Add the roadmap agents: translator agents that search foreign-language literature by gene +
  HGVS variant name, and a hand-drawn regional-focus tool for founder-population studies.

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
answer hidden (**top-1 100% / top-5 100%** on 15 cases). The heavy agents run on Meta's
**open-weight** Muse Spark model; **AWS** is the backbone. Live:
https://navigator-genome.abacusai.cloud · Repo:
https://github.com/troy214/navigator-genome-pilot
