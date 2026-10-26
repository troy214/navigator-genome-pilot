# Status — knowledge-category tracker

Tracked with the same four categories Navigator enforces. As of scaffold creation
(Oct 26, 2026), nothing here is Verified.

| Component | Category | Evidence needed to advance |
|-----------|----------|----------------------------|
| Repo structure | Implemented | — |
| Agent interfaces (base + 8 stubs) | Designed | Real model calls returning structured evidence |
| Meta Model API client | Designed | A successful live call with a real key |
| Coordinator pipeline | Designed | End-to-end run producing a dossier on the demo case |
| VCF intake | Idea | Implementation + a parsed real VCF |
| Benchmark scoring | Designed | top-1/top-5 computed on >=3 solved cases |
| Demo web app | Designed | Running app showing agent board + dossier |
| AWS deployment | Idea | Deployed orchestrator + S3 dossier storage |

**Rule:** do not advance a row's category without the evidence in the right column.
