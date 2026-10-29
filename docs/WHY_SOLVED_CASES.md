# Why benchmark on already-solved cases?

**Short version:** Solved cases are the measuring stick, not the product. You can only
prove a research method works where the truth is already known — and the same pipeline
then runs unchanged on genomes that have no answer yet. That is the value.

---

## The argument, for the submission writeup

**1. You can only validate a method where ground truth exists.**
Every trustworthy diagnostic or research tool — every clinical assay, every ML model — is
validated against known answers before anyone relies on it on the unknown. A solved case
(CF / CFTR, Wilson / ATP7B, PKU / PAH) has a published, confirmed answer. When we *hide*
that answer, run Navigator blind, and it independently lands on the correct gene and variant
**with a defensible evidence trail**, we have measured something real: not "did it guess
right," but "does the research protocol reliably assemble the correct evidence." That is what
earns the right to point it at a genome nobody has solved.

**2. The deliverable is the evidence process, not the answer.**
On a solved case the answer is already in a database — reproducing it is not the point.
Navigator is valuable because it shows its *work*: normalize → filter on population frequency
→ map phenotype to HPO → retrieve real citations → check ClinVar / gnomAD → red-team the
conclusion → assemble a sourced dossier with explicit uncertainty. That reasoning pipeline is
exactly what a researcher needs on an **unsolved** case, where there is no database answer to
look up. Benchmarking on solved cases proves the pipeline is sound so it can be trusted where
there is no safety net.

**3. Solved-case validation is a deliberate scope choice, not a limitation.**
Testing on already-solved public cases first avoids patient-privacy and consent problems while
the protocol is built and hardened — then a clinical partner and genuinely undiagnosed cases
come next. The "Submit a new case" path is the bridge: the **same pipeline**, now fed a genome
the system has never seen. Today that is an unknown demo VCF; with a clinical partner it is a
real undiagnosed patient. The solved-case benchmark is what makes that next step credible.

---

## One-line framing for a slide

> We benchmark on solved cases with the answer hidden to prove the research protocol is
> reliable — and the exact same protocol runs unchanged on a brand-new case. The value is a
> trustworthy evidence engine for genomes that don't yet have an answer.

*Research use only — not a diagnostic system, not medical advice.*
