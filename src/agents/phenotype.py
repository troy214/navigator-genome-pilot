"""Agent 3 — Phenotype (HPO). Map clinical picture to phenotype terms.
Status: SCAFFOLD (Designed).
"""
from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult


class PhenotypeAgent(BaseAgent):
    name = "phenotype"
    model = "muse-spark"

    @property
    def system_prompt(self) -> str:
        return (
            "You map a free-text clinical summary to standardized HPO phenotype terms. Return "
            "term IDs + labels with a confidence label each. Flag ambiguous mappings; do not "
            "over-claim."
        )

    def run(self, case: CaseInput, context: dict) -> AgentResult:
        # TODO: map case.clinical_summary -> HPO terms.
        return AgentResult(agent=self.name, notes="scaffold: not implemented")
