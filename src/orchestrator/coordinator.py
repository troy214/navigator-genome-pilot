"""Navigator coordinator. Passes clean structured JSON between isolated agents.

Each agent gets only the context it needs — never the whole shared chat. The Red Team
runs in an isolated context that receives the raw evidence WITHOUT any leading hypothesis.
Per-run output (agent results + dossier path + timings) is persisted to data/runs/.
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from config import settings
from src.agents.intake import IntakeAgent
from src.agents.filtering import FilteringAgent
from src.agents.phenotype import PhenotypeAgent
from src.agents.literature import LiteratureAgent
from src.agents.database import DatabaseAgent
from src.agents.case_matching import CaseMatchingAgent
from src.agents.red_team import RedTeamAgent
from src.agents.dossier_writer import DossierWriterAgent
from src.utils.schema import CaseInput, AgentResult
from src.utils.redaction import redact


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

    def run(self, case: CaseInput, persist: bool = True, progress=None) -> dict:
        t_start = time.time()
        results: list[AgentResult] = []
        ctx: dict = {}

        def step(agent, key, local_ctx=None):
            if progress:
                progress(agent.name, "working")
            r = agent.run(case, local_ctx if local_ctx is not None else ctx)
            results.append(r)
            ctx[key] = r.payload
            if progress:
                progress(agent.name, r.status)
            return r

        # 1-2: intake -> filtering
        step(self.intake, "intake")
        step(self.filtering, "filtering")
        # 3: phenotype (clinical summary)
        step(self.phenotype, "phenotype")
        # 4-6: world-knowledge + matching
        step(self.literature, "literature")
        step(self.database, "database")
        step(self.case_matching, "case_matching")

        # 7: red team — ISOLATED context, raw evidence only, no leading hypothesis
        all_evidence = [e.model_dump(mode="json") for res in results for e in res.evidence]
        rt = self.red_team.run(case, {"evidence": all_evidence})
        results.append(rt)
        ctx["red_team"] = rt.payload
        if progress:
            progress(self.red_team.name, rt.status)

        # collect all evidence (incl. red team) + unavailable sources for the dossier
        all_evidence = [e.model_dump(mode="json") for res in results for e in res.evidence]
        sources_unavailable = sorted({s for res in results for s in res.sources_unavailable})
        ctx["all_evidence"] = all_evidence
        ctx["sources_unavailable"] = sources_unavailable

        # 8: dossier writer
        step(self.dossier_writer, "dossier_writer")
        dossier_result = results[-1]

        total = round(time.time() - t_start, 3)
        out = {
            "case_id": case.case_id,
            "provider": settings.active_provider()["name"],
            "status": "complete",
            "total_elapsed_s": total,
            "timings": {r.agent: r.elapsed_s for r in results},
            "agent_results": [r.model_dump(mode="json") for r in results],
            "evidence_ledger": all_evidence,
            "sources_unavailable": sources_unavailable,
            "dossier": dossier_result.payload.get("dossier", {}),
            "pdf_path": dossier_result.payload.get("pdf_path"),
            "s3_destination": dossier_result.payload.get("s3_destination"),
        }

        if persist:
            self._persist(out)
        return out

    @staticmethod
    def _persist(out: dict) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = settings.RUNS_DIR / f"{out['case_id']}_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)
        # Redact before writing the run log.
        blob = redact(json.dumps(out, indent=2, default=str))
        (run_dir / "run.json").write_text(blob)
