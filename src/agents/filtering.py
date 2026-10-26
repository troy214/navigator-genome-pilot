"""Agent 2 — Filtering. Reduce candidate variants by frequency / quality.
Status: SCAFFOLD (Designed).
"""
from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult


class FilteringAgent(BaseAgent):
    name = "filtering"
    model = "meta-models/muse-spark-open-1026"

    @property
    def system_prompt(self) -> str:
        return (
            "You filter candidate variants. Apply population-frequency and quality heuristics to "
            "shrink the candidate list. Explain each exclusion with a reason. Do not rank for "
            "pathogenicity here — only reduce noise."
        )

    def run(self, case: CaseInput, context: dict) -> AgentResult:
        # TODO: implement frequency/quality filtering (optionally Exomiser upstream).
        return AgentResult(agent=self.name, notes="scaffold: not implemented")
