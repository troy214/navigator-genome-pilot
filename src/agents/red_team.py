"""Agent 7 — Red Team. Challenge conclusions, flag uncertainty.
Runs in an INDEPENDENT, isolated context to prevent confirmation bias.
Status: SCAFFOLD (Designed).
"""
from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult


class RedTeamAgent(BaseAgent):
    name = "red_team"
    model = "muse-spark"

    @property
    def system_prompt(self) -> str:
        return (
            "You are an independent skeptic. Given the assembled evidence, argue against the "
            "leading hypothesis: missing evidence, alternative explanations, overstated "
            "confidence, unsourced claims. Output explicit uncertainty labels."
        )

    def run(self, case: CaseInput, context: dict) -> AgentResult:
        # TODO: critique context['evidence']; downgrade confidence where unsupported.
        return AgentResult(agent=self.name, notes="scaffold: not implemented")
