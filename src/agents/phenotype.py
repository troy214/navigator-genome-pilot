"""Agent 3 — Phenotype (HPO). Map clinical free-text to real HPO terms.

LLM extracts candidate phenotype phrases; each is VALIDATED against the real HPO
(JAX ontology API) so we only ever emit genuine HP:IDs + official labels.
"""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.clients import hpo
from src.utils.schema import CaseInput, AgentResult, Evidence, Confidence, Knowledge


class PhenotypeAgent(BaseAgent):
    name = "phenotype"

    @property
    def system_prompt(self) -> str:
        return (
            "You extract clinical phenotype phrases from a free-text summary so they can be "
            "mapped to the Human Phenotype Ontology (HPO). Return concise, standard clinical "
            "phrases. Do not diagnose. Do not invent findings not in the text."
        )

    def _run(self, case: CaseInput, context: dict) -> AgentResult:
        evidence: list[Evidence] = []
        unavailable: list[str] = []
        phrases: list[str] = []

        if case.clinical_summary:
            out = self.client.complete_json(
                self.system_prompt,
                f"Clinical summary:\n{case.clinical_summary}\n\n"
                'Return JSON: {"phenotypes": ["phrase", ...]} with 3-10 concise phrases.',
                default={"phenotypes": []})
            if out.get("_unavailable"):
                unavailable.append("LLM (phenotype extraction)")
            phrases = [p for p in out.get("phenotypes", []) if isinstance(p, str)]

        # Also honor any HPO phrases/terms supplied directly on the case.
        phrases += [p for p in case.hpo_terms if not p.upper().startswith("HP:")]
        preset_ids = [p for p in case.hpo_terms if p.upper().startswith("HP:")]

        mapped: list[dict] = []
        seen_ids = set()
        for phrase in phrases:
            term = hpo.search_term(phrase)
            if term and term["id"] not in seen_ids:
                seen_ids.add(term["id"])
                mapped.append(term)
                evidence.append(Evidence(
                    claim=f"Phenotype '{phrase}' -> {term['id']} {term['name']}.",
                    source=term["source"], confidence=Confidence.MODERATE,
                    knowledge=Knowledge.VERIFIED, agent=self.name))
            elif not term:
                evidence.append(Evidence(
                    claim=f"Could not map phenotype phrase '{phrase}' to an HPO term (unknown).",
                    source="HPO (JAX ontology API)", confidence=Confidence.UNCERTAIN,
                    knowledge=Knowledge.UNKNOWN, agent=self.name))

        for hp_id in preset_ids:
            if hp_id not in seen_ids:
                mapped.append({"id": hp_id, "name": "(supplied)", "source": "case input"})

        status = "degraded" if unavailable else "done"
        return AgentResult(
            agent=self.name, status=status, evidence=evidence,
            notes=f"mapped {len(mapped)} HPO term(s)",
            payload={"hpo_terms": mapped}, sources_unavailable=unavailable)
