"""Agent 6 — Case-Matching. Compare the case to a bundled library of solved cases.

Similarity = Jaccard over phenotype labels + a gene-match bonus. Matches are reported as
HYPOTHESES with a rationale and confidence — never as conclusions.
"""
from __future__ import annotations
import json
from functools import lru_cache

from config import settings
from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult, Evidence, Variant, Confidence, Knowledge

LIBRARY = settings.ROOT / "benchmarks" / "library" / "solved_cases.json"


@lru_cache(maxsize=1)
def _library() -> list[dict]:
    try:
        return json.loads(LIBRARY.read_text()).get("cases", [])
    except Exception:
        return []


def _norm(s: str) -> str:
    return s.strip().lower()


class CaseMatchingAgent(BaseAgent):
    name = "case_matching"

    @property
    def system_prompt(self) -> str:
        return (
            "You compare a case to known solved cases and report closest matches as hypotheses "
            "with a similarity rationale and confidence. Matches are hypotheses, not conclusions."
        )

    def _run(self, case: CaseInput, context: dict) -> AgentResult:
        variants = [Variant(**v) for v in context.get("filtering", {}).get("variants", [])]
        case_genes = {_norm(v.gene) for v in variants if v.gene}
        pheno = context.get("phenotype", {}).get("hpo_terms", [])
        case_pheno = {_norm(t.get("name", "")) for t in pheno if t.get("name")}

        scored = []
        for ref in _library():
            ref_pheno = {_norm(p) for p in ref.get("phenotypes", [])}
            inter = case_pheno & ref_pheno
            union = case_pheno | ref_pheno
            jacc = len(inter) / len(union) if union else 0.0
            gene_match = _norm(ref.get("gene", "")) in case_genes
            score = jacc + (0.5 if gene_match else 0.0)
            if score > 0:
                scored.append((score, jacc, gene_match, inter, ref))

        scored.sort(key=lambda x: x[0], reverse=True)
        evidence: list[Evidence] = []
        matches = []
        for score, jacc, gene_match, inter, ref in scored[:3]:
            conf = (Confidence.MODERATE if score >= 0.5 else
                    Confidence.LOW if score >= 0.2 else Confidence.UNCERTAIN)
            shared = ", ".join(sorted(inter)) or "none"
            rationale = (f"phenotype overlap {jacc:.2f} (shared: {shared})"
                         + ("; gene matches" if gene_match else ""))
            evidence.append(Evidence(
                claim=f"Hypothesis: resembles {ref['disease']} ({ref['gene']}, "
                      f"{ref['variant']}) — {rationale}.",
                source=f"solved-case library:{ref['id']}", confidence=conf,
                knowledge=Knowledge.IDEA, agent=self.name, gene=ref["gene"]))
            matches.append({"id": ref["id"], "disease": ref["disease"], "gene": ref["gene"],
                            "variant": ref["variant"], "score": round(score, 3),
                            "shared_phenotypes": sorted(inter)})

        if not matches:
            evidence.append(Evidence(
                claim="No sufficiently similar solved case in the bundled library (unknown).",
                source="solved-case library", confidence=Confidence.UNCERTAIN,
                knowledge=Knowledge.UNKNOWN, agent=self.name))

        return AgentResult(
            agent=self.name, status="done", evidence=evidence,
            notes=f"{len(matches)} candidate match(es)", payload={"matches": matches})
