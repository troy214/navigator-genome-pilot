# Navigator Genome Pilot

**An agentic research tool that interprets genome variants and assembles evidence dossiers for researchers and clinicians.**

> ## Research use only — not a diagnostic system
> This project is a **research tool**. It interprets genome variants and assembles
> evidence dossiers for researchers and clinicians. **It is not a diagnostic system and
> does not give medical advice to any patient or end user.** It is benchmarked only on
> already-solved, published public cases with the answer hidden — it measures a research
> protocol, not advice to any person. Every output carries explicit uncertainty labels and
> is intended as decision *support* for an expert, never a diagnosis.

Built for the **Meta Global AI Developer Hackathon** (Indie Developer track). In production,
all runtime agents use Meta's models via the Meta Model API and partner inference (Modal /
Baseten). **AWS is the infrastructure backbone** (orchestration, storage, the demo app,
dossier storage).

**Live demo:** https://navigator-genome.abacusai.cloud

---

## What it does

Given a candidate variant list (VCF or a structured case) plus a clinical picture, eight
specialized agents independently investigate the case and a coordinator assembles a sourced,
uncertainty-labeled **evidence dossier** (rendered to PDF). The pilot is scored on
already-solved public benchmark cases (answer hidden) for top-1 / top-5 hit rate.

Current benchmark (Meta Muse Spark — `muse-spark-1.3` + open-weight `muse-spark-1.3-contributor`):
**top-1 = 100%, top-5 = 100%** over 15 solved cases (CF/CFTR, DMD, FH/LDLR, HBOC/BRCA1, HD/HTT,
HEMA/F8, MFS/FBN1, PKU/PAH, POMPE/GAA, RETT/MECP2, SCD/HBB, SMA/SMN1, TSD/HEXA, VHL, Wilson/ATP7B)
— every expected gene ranked #1 across 63 real Meta completions, zero failures. The three
high-volume agents (intake, filtering, database) run on the open-weight model. See
`benchmarks/results/report_meta.md`.

## The 8-agent pilot

| # | Agent | Role | Real data source |
|---|-------|------|------------------|
| 1 | Intake | Parse VCF / case, normalize variants | streaming VCF parser (`src/pipeline/vcf.py`) |
| 2 | Filtering | Reduce candidates by frequency / quality | allele-frequency heuristics, explains each exclusion |
| 3 | Phenotype (HPO) | Map clinical text to HPO terms | **HPO / JAX ontology API** (LLM extracts, HPO validates) |
| 4 | Literature | Search + summarize publications | **Europe PMC REST** — every claim carries a PMID/DOI |
| 5 | Database | Query variant/disease databases | **MyVariant.info + ClinVar (NCBI) + gnomAD GraphQL** |
| 6 | Case-Matching | Compare against known solved cases | bundled solved-case library, similarity + rationale |
| 7 | Red Team | Challenge evidence, flag uncertainty | **isolated context** — never sees a leading hypothesis |
| 8 | Dossier Writer | Assemble physician-facing dossier + PDF | reportlab PDF with research-use-only footer |

Each agent runs in its own private context. The **coordinator** passes clean, structured
JSON between them — no shared chat window. See `docs/ARCHITECTURE.md`.

## Knowledge discipline (from Project Navigator)

Every claim (every Evidence row) is tagged **Idea / Designed / Implemented / Verified** — or
explicitly **Unknown**: the system must be able to say when it does not know. Absent database
records are labelled *absent*, never silently treated as *benign*. When an external source is
down, the dossier says so instead of guessing. This repo's own status is tracked the same way
in `docs/STATUS.md`.

## Architecture at a glance

- **Agents' compute (production):** Meta models via Meta Model API + Modal/Baseten (isolation per agent)
- **Agents' compute (dev, now):** this VM's OpenAI-compatible endpoint — proves the logic end-to-end
- **Orchestration, storage, demo app, dossier storage:** **AWS** backbone (see `infra/aws/`)

## Dev vs Meta provider switch (one env change)

The model client reads its provider from `config/settings.py` + environment:

- **No `META_MODEL_API_KEY` set →** provider `dev`: base_url `https://routellm.abacus.ai/v1`,
  key from `$ABACUS_API_KEY`, model `gpt-5.4-mini` (`config/models.dev.yaml`).
- **`META_MODEL_API_KEY` set →** provider `meta`: Meta Model API, agent→model map from
  `config/agents.yaml` — five agents on `muse-spark-1.3`, three high-volume agents on open-weight
  `muse-spark-1.3-contributor` (both verified live on the Meta Model API).

**To transpose to Meta: set one env var.**

```bash
export META_MODEL_API_KEY=<your-meta-key>
# optional overrides:
export META_MODEL_API_BASE_URL=https://api.meta.ai/v1
```

No agent code mentions a model name — see `docs/TRANSPOSE_TO_META.md` for the full checklist.

## Repo layout

```
src/agents/        the 8 agent implementations (real)
src/orchestrator/  coordinator (isolated-context pipeline) + run CLI
src/models/        provider-switching model client + model resolver
src/clients/       free bio-data API clients (Europe PMC, MyVariant, ClinVar, gnomAD, HPO)
src/pipeline/      streaming VCF parser + dossier PDF renderer
src/utils/         schema, redaction, cache, polite HTTP
benchmarks/        solved public cases + hidden answers + scoring harness + solved-case library
app/               demo web UI (agent board + evidence ledger + dossier view) + FastAPI backend
config/            agents.yaml (Meta map), models.dev.yaml (dev map), settings.py
deploy/            systemd unit + nginx vhost + install.sh
infra/aws/         AWS deployment notes/templates
docs/              architecture, status, compliance, demo script, transpose-to-Meta
tests/             offline test suite (LLM + HTTP mocked)
```

## Quick start

```bash
pip install -r requirements.txt
# No .env needed on this VM — the dev provider uses $ABACUS_API_KEY automatically.

# Run the full pipeline on a real solved case -> prints a summary + writes a PDF dossier:
python -m src.orchestrator.run --case benchmarks/cases/cystic_fibrosis.json

# Score all benchmark cases (top-1 / top-5):
python -m benchmarks.score

# Run the offline test suite (no network):
pytest -q

# Serve the demo app locally:
python -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8077
```

## Deploy (this VM)

```bash
bash deploy/install.sh     # symlinks systemd unit + nginx vhost, starts uvicorn, health-checks
```

Live at **https://navigator-genome.abacusai.cloud**. The dev provider key is read from
`deploy/navigator.env` (gitignored — never committed).

## Hackathon compliance

See `docs/COMPLIANCE.md` for the framing that must appear consistently in the README, demo
video, and in-product copy. `docs/DEMO_SCRIPT.md` is a shot-by-shot 3-minute demo script.

## License

MIT — see `LICENSE`. Review each third-party data source's own terms before relying on it.
