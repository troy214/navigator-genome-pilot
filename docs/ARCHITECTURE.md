# Architecture

## Principle: isolated agents, structured hand-off

Each of the 8 agents runs in its own private context with a focused prompt and only the
inputs it needs. The **coordinator** passes clean JSON between them — there is no shared
chat window. This prevents context bloat, cuts token cost, and (critically) prevents
confirmation bias: the Red Team agent evaluates evidence without being told the leading
hypothesis.

```
            +-------------------- Coordinator (Navigator) --------------------+
            |                                                                 |
  CaseInput | 1 Intake -> 2 Filtering -> 3 Phenotype                           |
   (VCF /   |      \\                        |                                 |
   demo +   |       +--> 4 Literature  5 Database  6 Case-Matching            |
   clinical |                         (each gets filtered variants + HPO)     |
   summary) |                              |                                   |
            |                     assembled evidence                         |
            |                              v                                  |
            |                       7 Red Team (isolated critique)            |
            |                              v                                  |
            |                       8 Dossier Writer --> Evidence Dossier PDF |
            +-----------------------------------------------------------------+
```

## Compute split

- **Agent inference:** Meta models via Meta Model API; open-weight agents (intake, filtering,
  database) can run on Modal / Baseten to control cost and qualify for the open-weights bonus.
- **Orchestration, storage, demo app, dossier storage:** Troy's existing **AWS** infrastructure.

## Knowledge discipline

Every `Evidence` record carries a `knowledge` tag (idea / designed / implemented / verified /
unknown) and a `confidence` label, and MUST have a `source`. The system is required to output
`unknown` rather than guess. See `src/utils/schema.py`.

## Data boundary

No real private patient data in the pilot. Benchmarks use published, already-solved public
cases with the answer hidden. `src/utils/redaction.py` scrubs secrets/PII before logging.
