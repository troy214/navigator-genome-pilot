# 3-minute demo video — shot-by-shot script

Read this aloud while screen-recording. Target: **3:00**. Live demo URL:
**https://navigator-genome.abacusai.cloud**. Have one benchmark case ready to run.

> Keep the research-tool framing explicit at the start AND end — it is the compliance line.

---

## [0:00–0:20] Hook + framing  *(on camera or voiceover over the app header)*

> "This is **Navigator Genome Pilot** — an agentic **research tool** that interprets genome
> variants and assembles an evidence dossier for researchers and clinicians. To be clear up
> front: it is **not a diagnostic system and it does not give medical advice**. It's decision
> support, benchmarked only on already-solved public cases — and every claim it makes is
> sourced and carries an uncertainty label."

*Shot: the app header with the amber "Research use only" banner visible.*

## [0:20–0:40] The problem + the idea

> "Variant interpretation means cross-checking genetics databases, population frequencies,
> phenotype ontologies, and the literature — then arguing with yourself about what's actually
> supported. Navigator runs that as **eight specialized agents**, each in its own isolated
> context, coordinated into one sourced dossier."

*Shot: the 8-agent board, all tiles "idle".*

## [0:40–1:30] Run the pipeline — the core moment

> "I'll run a real solved case — a toddler with recurrent respiratory infections, failure to
> thrive, and salty sweat. I click **Run pipeline**."

*Shot: select `CF-CFTR-F508del`, click Run. Tiles turn amber "working" → green "done".*

> "Watch the agents light up. Intake parsed the VCF. Filtering **excluded a common variant**,
> MUC5B, because its population frequency is too high for a rare disease — and it tells you
> why. Phenotype mapped the clinical text to real **HPO terms**. Literature hit **Europe PMC**,
> Database queried **ClinVar, gnomAD and MyVariant** — all live, free, public APIs. And the
> **Red Team** agent ran in an isolated context to argue against the evidence."

*Shot: point at the agent tiles' status notes as they complete (~10s total).*

## [1:30–2:15] The evidence ledger + knowledge discipline

> "Here's what makes this a Navigator project: the **evidence ledger**. Every single row has a
> **source** and two labels — a **confidence** level and a **knowledge category**: is this
> Verified, Implemented, or genuinely Unknown? When ClinVar has no record, we label it
> **absent — not benign**. When an API is down, the dossier says so. The system is built to
> **say when it doesn't know.**"

*Shot: scroll the evidence ledger; hover a row with a PMID source and a "verified" tag, and
one with an "unknown" tag.*

## [2:15–2:45] The dossier + the result

> "The Dossier Writer assembles everything into a ranked, physician-facing dossier. Top
> candidate: **CFTR, F508del** — the correct answer — with supporting literature citations,
> contradicting evidence, and an explicit uncertainty label. One click downloads the **PDF**,
> footer carries the research-use notice. Across our benchmark of solved cases, top-1 accuracy
> is **100%** — and that's on the dev model, before touching Meta's."

*Shot: the dossier panel, then click "Download dossier PDF" and show the PDF's first page.*

## [2:45–3:00] Meta + AWS + close

> "In production the eight agents run on **Meta's models** — the open-weight Muse Spark models
> for the heavy-volume agents — and the whole backbone runs on **AWS**. Swapping from our dev
> endpoint to Meta is **one environment variable**. That's Navigator Genome Pilot: a sourced,
> self-skeptical research tool that knows the difference between what it knows and what it
> doesn't. Thanks for watching."

*Shot: back to the app header / the STATUS.md knowledge table.*

---

### Pre-record checklist
- [ ] Run the case once before recording so API responses are cached (fast, repeatable run).
- [ ] Confirm the live URL loads and provider pill shows the expected provider.
- [ ] Have the downloaded PDF ready to show in case the live download is slow.
- [ ] Say "research tool / not a diagnostic system" in BOTH the intro and the outro.
- [ ] Keep total runtime under 3:00.
