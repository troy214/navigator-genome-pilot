# Navigator Genome Pilot

**An agentic research tool that interprets genome variants and assembles evidence dossiers for researchers and clinicians.**

> ## Research use only — not a diagnostic system
> This project is a **research tool**. It interprets genome variants and assembles
> evidence dossiers for researchers and clinicians. **It is not a diagnostic system and
> does not give medical advice to any patient or end user.** It is benchmarked only on
> already-solved, published public cases with the answer hidden — it measures a research
> protocol, not advice to any person. Every output carries explicit uncertainty labels and
> is intended as decision *support* for an expert, never a diagnosis.

Built for the **Meta Global AI Developer Hackathon** (Indie Developer track). All runtime
agents use Meta's models via the Meta Model API and partner inference (Modal / Baseten).

---

## What it does

Given a candidate variant list (VCF or a demo case) plus a clinical picture, a swarm of
eight specialized agents independently investigate the case and a coordinator assembles a
sourced, uncertainty-labeled **evidence dossier**. The pilot is scored on already-solved
public benchmark cases (answer hidden) for top-1 / top-5 hit rate.

## The 8-agent pilot

| # | Agent | Role |
|---|-------|------|
| 1 | Intake | Parse VCF / demo case, normalize variants |
| 2 | Filtering | Reduce candidates by frequency / quality |
| 3 | Phenotype (HPO) | Map clinical picture to phenotype terms |
| 4 | Literature | Search + summarize relevant publications |
| 5 | Database | Query OMIM / Orphanet / ClinVar / gnomAD |
| 6 | Case-Matching | Compare against known solved cases |
| 7 | Red Team | Challenge conclusions, flag uncertainty (isolated context) |
| 8 | Dossier Writer | Assemble the physician-facing evidence dossier |

Each agent runs in its own private context. The **orchestrator** passes clean, structured
JSON between them — no shared chat window. See `docs/ARCHITECTURE.md`.

## Knowledge discipline (from Project Navigator)

Every claim the system produces is tagged as one of: **Idea / Designed / Implemented /
Verified**, and the system must say when it does not know. This repo's own status is tracked
the same way in `docs/STATUS.md` — right now almost everything here is **Scaffold (Designed)**,
not Verified.

## Architecture at a glance

- **Agents' compute:** Meta models via Meta Model API + Modal/Baseten sandboxes (isolation per agent)
- **Orchestration, storage, demo app:** Troy's existing **AWS** infrastructure
- This keeps agent inference on hackathon credits while the backbone stays on AWS.

## Repo layout

```
src/agents/        the 8 agent implementations (stubs)
src/orchestrator/  the coordination loop
src/models/        Meta Model API client wrapper
src/pipeline/      VCF intake + variant handling
src/utils/         shared helpers (logging, schema, redaction)
benchmarks/        solved public cases + scoring harness
app/               demo web UI (agent board + evidence ledger + dossier view)
config/            model-to-agent mapping, settings
infra/aws/         AWS deployment notes/templates
docs/              architecture, status, compliance
tests/             tests
```

## Quick start (scaffold)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # fill in your own keys locally — never commit .env
python -m src.orchestrator.run --case benchmarks/cases/demo_case.json
```

## Hackathon compliance

See `docs/COMPLIANCE.md` for the framing that must appear consistently in the README, demo
video, and in-product copy. New work only (Oct 27 – Nov 4); public repo; 3-minute demo video.

## License

MIT — see `LICENSE`. Review before relying on any third-party data source's own terms.
