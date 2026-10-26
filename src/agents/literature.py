"""Agent 4 — Literature. Search and summarize relevant publications.
Status: SCAFFOLD (Designed).
"""
from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult


class LiteratureAgent(BaseAgent):
    name = "literature"
    model = "muse-spark"

    @property
    def system_prompt(self) -> str:
        return (
            "You find and summarize publications relevant to a gene + variant + phenotype. "
            "Search by gene and HGVS (language-independent) to reach foreign-language sources. "
            "Every summarized claim MUST carry a citation. No citation, no claim."
        )

    def run(self, case: CaseInput, context: dict) -> AgentResult:
        # TODO: PubMed / Europe PMC search; translate; summarize with citations.
        return AgentResult(agent=self.name, notes="scaffold: not implemented")
