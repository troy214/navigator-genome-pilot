# Demoing the genomic data layer — scaling & how to show it works

## 1. The scaling question, answered with real measurements

Measured on this VM (gate only — deterministic, no agents), synthetic VCFs,
`drop_common=True`, top-200 candidates:

| Variants | Time (all stages) | µs / variant |
|---------:|------------------:|-------------:|
|   10,000 |             3.5 s |          355 |
|   50,000 |            17.4 s |          348 |
|  200,000 |            71.6 s |          358 |

Scaling is **cleanly linear** (~358 µs/variant, no meaningful fixed overhead).
So the napkin math is basically right — but the real number is ~30 min, not ~20:

- **~100k variants (a typical exome / WES): ~35 s**
- **~1M variants: ~6 min**
- **~5M variants (a typical whole genome / WGS): ~30 min**

## 2. Where the time actually goes (this matters for the demo)

Breaking the 50k run (17.4 s) down by stage:

| What runs | Time (50k) |
|---|---:|
| Normalize + QC + **rarity rank** (the actual *reduction*) | **0.8 s** |
| Annotation join (gnomAD/ClinVar lookups over variants) | ~16.6 s |

**The reduction that protects the agents is sub-second. Almost all the wall-clock
is the annotation join** — and annotation currently runs over *all* variants, even
though only the ~200 survivors ever reach the agents. Reordering to annotate *after*
rank (survivors only) is a clear, safe optimization that would cut full-genome time
dramatically. We present the measured reality today and keep that headroom in reserve.

## 3. How to show it actually works in the demo (recommended)

Don't run 5M variants live — nobody waits 30 minutes, and you don't need to.

**A. Live, on a realistic exome (recommended headline).**
Upload a ~100k-variant WES VCF. In ~35 seconds the data layer shows the reduction on
screen — e.g. *"110,000 variants → 5,047 failed QC → 198 rare candidates"* — and only
then do the 8 agents run, on a tractable set. This is the whole thesis, live and honest.

**B. Pre-computed whole-genome artifact (for the WGS claim).**
Run a real ~5M-variant WGS file ahead of time and show the saved result: the candidate
count, the run timing, and the `data_layer` note in the run. Then run the agents on the
reduced set live. This proves it works at genome scale without a 30-minute pause.

**C. The small gated run already live.**
Every VCF uploaded through "Submit a new case" now carries a `data_layer` note showing
`candidates_after_gate`. Even the 3-variant sample demonstrates the gate is in the path.

## 4. The honest framing to say out loud

> "The data layer reduces a whole genome deterministically before any agent sees a
> variant. The reduction itself is sub-second per 50k variants; a full genome is a
> ~30-minute batch step — in line with standard clinical bioinformatics pipelines,
> which run for hours — and the agents then reason over ~200 candidates, not millions.
> For a live demo we run an exome end-to-end in under a minute, and show a pre-computed
> whole-genome run for scale."

Why 30 min is not a weakness: real variant-calling and annotation pipelines (GATK,
VEP, etc.) routinely take hours per genome. A 30-minute deterministic reduction that
is logged, reproducible, and hands the agents a clean candidate set is the *point* —
it moves the heavy, auditable work out of expensive, non-reproducible LLM reasoning.

*Research use only — not a diagnostic system, not medical advice.*
