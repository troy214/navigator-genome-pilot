"""Agent 5 — Database. Query OMIM / Orphanet / ClinVar / gnomAD.
Status: SCAFFOLD (Designed).
"""
from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult


class DatabaseAgent(BaseAgent):
    name = "database"
    model = "meta-models/muse-spark-open-1026"

    @property
    def system_prompt(self) -> str:
        return (
            "You query curated variant/disease databases and return structured records with "
            "source + version. Distinguish an absent record from a benign record. Never fabricate "
            "a database entry."
        )

    def run(self, case: CaseInput, context: dict) -> AgentResult:
        # TODO: ClinVar / gnomAD / OMIM / Orphanet lookups (respect each source's terms).
        return AgentResult(agent=self.name, notes="scaffold: not implemented")
