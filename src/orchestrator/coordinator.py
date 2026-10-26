"""Navigator coordinator. Passes clean structured JSON between isolated agents.

Status: SCAFFOLD (Designed). The pipeline order is wired; agent internals are stubs.
The coordinator never merges agents into one shared chat — each gets only what it needs.
"""
from __future__ import annotations

from src.agents.intake import IntakeAgent
from src.agents.filtering import FilteringAgent
from src.agents.phenotype import PhenotypeAgent
from src.agents.literature import LiteratureAgent
from src.agents.database import DatabaseAgent
from src.agents.case_matching import CaseMatchingAgent
from src.agents.red_team import RedTeamAgent
from src.agents.dossier_writer import DossierWriterAgent
from src.utils.schema import CaseInput, AgentResult


class Coordinator:
    def __init__(self):
        self.intake = IntakeAgent()
        self.filtering = FilteringAgent()
        self.phenotype = PhenotypeAgent()
        self.literature = LiteratureAgent()
        self.database = DatabaseAgent()
        self.case_matching = CaseMatchingAgent()
        self.red_team = RedTeamAgent()
        self.dossier_writer = DossierWriterAgent()

    def run(self, case: CaseInput) -> dict:
        """Run the 8-agent pilot and return the assembled dossier payload."""
        results: list[AgentResult] = []
        ctx: dict = {}

        # 1-2: intake -> filtering
        r = self.intake.run(case, ctx); results.append(r); ctx["intake"] = r.payload
        r = self.filtering.run(case, ctx); results.append(r); ctx["filtering"] = r.payload

        # 3: phenotype (needs only the clinical summary)
        r = self.phenotype.run(case, ctx); results.append(r); ctx["phenotype"] = r.payload

        # 4-6: world-knowledge + matching (each gets filtered variants + phenotype only)
        for agent, key in (
            (self.literature, "literature"),
            (self.database, "database"),
            (self.case_matching, "case_matching"),
        ):
            r = agent.run(case, ctx); results.append(r); ctx[key] = r.payload

        # 7: red team gets the assembled evidence, in an isolated context
        all_evidence = [e for res in results for e in res.evidence]
        r = self.red_team.run(case, {"evidence": [e.model_dump() for e in all_evidence]})
        results.append(r); ctx["red_team"] = r.payload

        # 8: dossier writer assembles the final artifact
        r = self.dossier_writer.run(case, ctx); results.append(r)

        return {
            "case_id": case.case_id,
            "agent_results": [res.model_dump() for res in results],
            "status": "scaffold",
        }
