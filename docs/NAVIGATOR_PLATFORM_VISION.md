# Navigator — One Architecture, Many Laboratories (for Meta)

> The rare-disease pilot you see today is **one laboratory** running on the Navigator
> architecture. The same architecture powers a family of verticals. They are **not separate
> platforms** — they are different laboratories wired to different data and expert knowledge,
> reasoning on the **same Meta-Muse-powered engine** and producing the **same kind of output:
> a ranked, sourced, uncertainty-labeled evidence dossier.**

---

## The core idea

Navigator is not fundamentally a "rare-disease hunter." It is a general pattern for a hard
class of problem: **too much raw evidence, too little time, and a decision that must be
explainable.** That pattern repeats across medicine, media, government, research, business,
and law. Navigator solves it once, as an architecture, and then specializes.

Every Navigator laboratory runs the same four-part spine:

1. **Deterministic data layer** — cheap, auditable, reproducible engineering reduces a huge
   raw input down to a small, ranked, well-provenanced candidate set **before any agent runs**.
2. **A swarm of specialized Meta-Muse agents** — each a narrow expert, running in isolated
   context, that reasons only over the reduced candidate set.
3. **An adversarial red-team agent** — an independent agent whose only job is to challenge the
   conclusions and surface uncertainty, so the output is never falsely confident.
4. **A dossier writer** — assembles a ranked, cited, uncertainty-labeled evidence dossier for
   a human expert to review. Navigator proposes and ranks; the human decides.

Meta's Muse models are the reasoning engine for every agent in every laboratory. Only the
**data sources, the expert panels, and the ranking heuristics** change from vertical to
vertical — the architecture, the isolation discipline, the red-team, and the dossier format
do not.

## The genome pilot, described as reusable primitives

The eight agents in the live pilot are not genome-specific ideas — they are **generic
reasoning roles** that happen to be pointed at genomic data:

| Pilot agent | Genome-specific job | The reusable primitive |
|---|---|---|
| Intake | Parse & normalize the VCF | **Ingest & normalize** any raw evidence stream |
| Filtering | Drop common/low-quality variants | **Reduce** the candidate set deterministically |
| Phenotype | Map symptoms to HPO terms | **Map the query** onto a controlled vocabulary |
| Literature | Search & summarize publications | **Search the published record** |
| Database | Query ClinVar / gnomAD / MyVariant | **Query authoritative structured sources** |
| Case Matching | Compare to solved cases | **Retrieve precedent / prior-art** |
| Red Team | Challenge, flag uncertainty | **Adversarial review** (vertical-independent) |
| Dossier Writer | Assemble the physician dossier | **Assemble the evidence dossier** (vertical-independent) |

Swap the data sources and the vocabulary, keep the spine, and you have a new laboratory.

## The laboratories

**Genome Navigator** *(live today)* — Reduces a genome to ranked variant candidates and
assembles a research hypothesis for a clinician/researcher. *Sources: ClinVar, gnomAD,
MyVariant, Europe PMC, HPO.* **Research use only — not a diagnosis.**

**Media Navigator** — Reduces a flood of articles, transcripts, posts and clips to the
claims that matter, retrieves what's been said before, red-teams for bias and
misattribution, and assembles a sourced briefing. *For newsrooms, analysts, monitoring.*

**Government Navigator** — Reduces statutes, filings, dockets, and public comment to the
provisions and precedents relevant to a question, with an adversarial check for
counter-arguments, and a cited policy dossier. *For legislative/regulatory analysis.*

**Research Navigator** — Reduces a literature corpus to the papers and findings that bear on
a hypothesis, retrieves prior work, challenges the evidence, and assembles a review-grade
dossier. *For scientific and technical literature review.*

**Corporate Intelligence Navigator** — Reduces filings, news, market and competitor signals
to the developments that matter, retrieves precedent, red-teams the thesis, and assembles a
decision-ready brief. *For strategy, diligence, competitive analysis.*

**Patent Navigator** — Reduces a patent/prior-art space to the references most relevant to a
claim, retrieves precedent, challenges novelty/obviousness, and assembles a prior-art
dossier. *For patent search, FTO, and invalidity analysis.*

## Why this matters for a platform story

- **Build once, specialize many.** The expensive, trustworthy parts — deterministic
  reduction, isolated expert agents, adversarial review, explainable dossier output — are
  built once and shared. A new vertical is a new *configuration* (sources + panels +
  heuristics), not a new platform.
- **Meta scales across all of it.** Every laboratory's reasoning runs on Meta Muse. More
  verticals mean more Meta-powered reasoning on the same proven engine.
- **The same governance everywhere.** Per-tenant API keys, hashed secrets, throttling and
  quotas, isolation between agents, and uncertainty-labeled output apply to every
  laboratory — so the responsible-AI posture generalizes with the architecture.
- **Proven, not hypothetical.** The spine is already validated: the genome laboratory scored
  **100% top-1 and 100% top-5** on 15 solved public cases across 66 real Meta completions.
  The other laboratories inherit that same spine.

## One honest boundary

Today, **one laboratory (Genome Navigator) is live and benchmarked.** The other four are
**architecturally ready** — they reuse the same spine, data-layer, agent-isolation, red-team,
and dossier primitives — but they are presented here as the **platform roadmap**, not as
shipped products. Navigator's claim is the architecture and its proof in one vertical, plus a
credible, low-risk path to the rest.
