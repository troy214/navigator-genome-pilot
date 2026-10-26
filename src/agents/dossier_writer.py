"""Agent 8 — Dossier Writer. Assemble the physician-facing evidence dossier.
Status: SCAFFOLD (Designed).
"""
from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult


class DossierWriterAgent(BaseAgent):
    name = "dossier_writer"
    model = "muse-spark"

    @property
    def system_prompt(self) -> str:
        return (
            "You assemble an evidence dossier for a researcher/clinician. Structure: candidate "
            "findings, supporting + contradicting evidence (with citations), and an explicit "
            "uncertainty label per finding. This is decision SUPPORT, not a diagnosis. Include "
            "the research-use-only notice."
        )

    def run(self, case: CaseInput, context: dict) -> AgentResult:
        # TODO: render structured dossier -> PDF (reportlab) stored on AWS S3.
        return AgentResult(agent=self.name, notes="scaffold: not implemented")
