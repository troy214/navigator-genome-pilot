"""Agent 6 — Case-Matching. Compare case against known solved cases.
Status: SCAFFOLD (Designed).
"""
from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult


class CaseMatchingAgent(BaseAgent):
    name = "case_matching"
    model = "muse-spark"

    @property
    def system_prompt(self) -> str:
        return (
            "You compare the current case to a library of known solved cases and report the "
            "closest matches with a similarity rationale and confidence. Matches are hypotheses, "
            "not conclusions."
        )

    def run(self, case: CaseInput, context: dict) -> AgentResult:
        # TODO: similarity over phenotype + gene sets vs. solved-case library.
        return AgentResult(agent=self.name, notes="scaffold: not implemented")
