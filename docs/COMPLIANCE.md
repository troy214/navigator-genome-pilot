# Hackathon compliance & framing

Use this framing CONSISTENTLY in the README, the 3-minute demo video, and in-product copy.
The Stage One judging check reads the submission (repo + live product + video), not the
application — acceptance does not pre-clear the project.

## The line not to cross

The anti-project list bans "any project using AI to generate and give medical advice." Stay
clearly on the research-tool side:

- Interprets variants and assembles **evidence dossiers for researchers/clinicians** — not advice to a patient.
- Benchmarked on **already-solved, published public cases** with the answer hidden — a research protocol, not advice to a person.
- Every output carries **uncertainty labels**; nothing is presented as a diagnosis.
- Theme fit: "Build for Your World" / "Push the Frontier" — an agentic research-acceleration platform.

## Drop-in notice (README + dossier footer + video intro)

> Research use only. This tool interprets genome variants and assembles evidence dossiers for
> researchers and clinicians. It is not a diagnostic system and does not provide medical advice.
> It is evaluated on already-solved public benchmark cases; all outputs carry uncertainty labels
> and are decision support for experts, not a diagnosis.

## Hard rules

- Must incorporate Meta's models (Muse Spark series / Muse Code / SAM 3.1 / open weights).
- Public repository.
- New work only (Oct 27 – Nov 4); clearly identify anything pre-existing.
- 3-minute demo video; submit on the CV platform by Nov 4, 9:00 PM ET.

## Dev-endpoint provability (honesty note)

The pilot currently runs on a **dev stand-in LLM endpoint** to prove the full pipeline logic
end-to-end before a Meta key is available. This is disclosed openly:

- In production the agents run on **Meta's models** (Muse Spark / Muse Spark open-weight). The
  swap is one environment variable — see `docs/TRANSPOSE_TO_META.md`.
- `docs/STATUS.md` marks the Meta-inference and AWS-deployment rows as **Designed**, not
  Verified, precisely because they have not yet been run in the production environment. We do
  not claim "Verified" for anything we have not actually executed.
- Everything benchmarked (top-1 / top-5) was measured on the dev endpoint and labelled as such.

## Verified compliance checklist (as built)

- [x] Research-use-only notice in README, app header, dossier PDF footer, and demo script.
- [x] Benchmarked only on already-solved, published public cases; answers hidden from agents.
- [x] Every evidence row carries a source + uncertainty label; nothing presented as a diagnosis.
- [x] System explicitly says when a source is unavailable / a record is absent (not benign).
- [x] AWS documented as the backbone; Meta models documented as production inference.
- [x] Live product: https://navigator-genome.abacusai.cloud
