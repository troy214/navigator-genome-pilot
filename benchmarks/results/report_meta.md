# Navigator Genome Pilot — Meta Model API Benchmark

> **RESEARCH USE ONLY.** Every output is a research hypothesis with explicit uncertainty — not a diagnosis and not medical advice. This benchmark runs over published, already-solved public cases to measure the system's ability to re-derive the known causal gene; it is not a clinical validation.

_Generated: 2026-10-30T17:26:59.473343+00:00_

## Verdict

**VALID META RUN** — this benchmark genuinely executed on `muse-spark-1.3` via the Meta Model API (`https://api.meta.ai/v1`).

- Proof gate (`real Meta completions succeeded > 0`): **PASSED** (succeeded = 66).

## Provider & model

- Provider: **meta**
- Model id: **muse-spark-1.3**
- Base URL: `https://api.meta.ai/v1`

## Real Meta completion calls (proof of genuine usage)

- Attempted: **66**
- Succeeded: **66**
- Failed / degraded: **0**
- Error classes: `none`

## Tokens

- Usage reported by API: **True**
- Prompt tokens: **31513**
- Completion tokens: **123655**
- Total tokens: **155168**

## Latency

- Total model latency: **680.805 s**
- Total wall-clock: **693.411 s**
- Mean per model call: **10.315 s**

## Aggregate score

- Cases scored: **15 / 15**
- Top-1 hit rate: **100%**
- Top-5 hit rate: **100%**

## Per-case results

| Case | Expected | Top-1 | Top-5 | Ranked (top 5) | Meta calls ✓/✗ | Sources unavailable |
|------|----------|-------|-------|----------------|----------------|---------------------|
| CF-CFTR-F508del | CFTR | ✓ | ✓ | CFTR | 4/0 | — |
| DMD-DMD-R1577X | DMD | ✓ | ✓ | DMD | 4/0 | — |
| FH-LDLR-G592E | LDLR | ✓ | ✓ | LDLR | 4/0 | — |
| HBOC-BRCA1-185delAG | BRCA1 | ✓ | ✓ | BRCA1 | 4/0 | — |
| HD-HTT-CAG-EXP | HTT | ✓ | ✓ | HTT | 4/0 | — |
| HEMA-F8-R2016W | F8 | ✓ | ✓ | F8 | 4/0 | — |
| MFS-FBN1-C1170Y | FBN1 | ✓ | ✓ | FBN1 | 4/0 | — |
| PKU-PAH | PAH | ✓ | ✓ | PAH, HEXA, MECP2 | 6/0 | — |
| POMPE-GAA-IVS1 | GAA | ✓ | ✓ | GAA, DMD | 5/0 | — |
| RETT-MECP2-T158M | MECP2 | ✓ | ✓ | MECP2, HEXA | 5/0 | — |
| SCD-HBB-E6V | HBB | ✓ | ✓ | HBB | 4/0 | — |
| SMA-SMN1-EX7DEL | SMN1 | ✓ | ✓ | SMN1, DMD | 5/0 | — |
| TSD-HEXA-1278insTATC | HEXA | ✓ | ✓ | HEXA, MECP2 | 5/0 | — |
| VHL-VHL-R167W | VHL | ✓ | ✓ | VHL | 4/0 | — |
| WILSON-ATP7B-H1069Q | ATP7B | ✓ | ✓ | ATP7B | 4/0 | — |

_"Meta calls ✓/✗" = real Meta completions that succeeded / failed (degraded to fallback) during that case. A valid Meta run requires ✓ > 0 overall._

---

_Navigator Genome Pilot is a research project. Outputs are hypotheses for research review, not clinical conclusions._