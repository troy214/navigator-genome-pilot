"""Agent 7 — Red Team. Independent skeptic in an ISOLATED context.

Receives ONLY the raw evidence rows — never the leading hypothesis framed as a conclusion.
Flags unsupported/unsourced claims, downgrades overstated confidence, emits uncertainty labels.
"""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult, Evidence, Confidence, Knowledge


class RedTeamAgent(BaseAgent):
    name = "red_team"

    @property
    def system_prompt(self) -> str:
        return (
            "You are an INDEPENDENT skeptic reviewing a list of evidence rows. You are deliberately "
            "NOT told any conclusion. For the evidence as a whole: identify unsourced or weak claims, "
            "alternative explanations, missing evidence, and any confidence that looks overstated. "
            "Be specific and reference claims. Do not endorse a diagnosis."
        )

    def _run(self, case: CaseInput, context: dict) -> AgentResult:
        rows = context.get("evidence", [])
        evidence: list[Evidence] = []
        unavailable: list[str] = []

        # Deterministic structural checks first (always run, no LLM needed).
        unsourced = [r for r in rows if not r.get("source") or r.get("source") == ""]
        if unsourced:
            evidence.append(Evidence(
                claim=f"{len(unsourced)} claim(s) lack a clear source and must be treated as "
                      f"unverified.", source="red_team:structural-check",
                confidence=Confidence.HIGH, knowledge=Knowledge.VERIFIED, agent=self.name))
        high_idea = [r for r in rows
                     if r.get("confidence") == "high" and r.get("knowledge") in ("idea", "unknown")]
        for r in high_idea:
            evidence.append(Evidence(
                claim=f"Confidence likely overstated: '{r.get('claim','')[:120]}' is tagged "
                      f"knowledge='{r.get('knowledge')}' yet high confidence — downgrade.",
                source="red_team:consistency-check", confidence=Confidence.MODERATE,
                knowledge=Knowledge.VERIFIED, agent=self.name))

        # LLM critique over the evidence summary (isolated — no conclusion provided).
        summary = "\n".join(f"- [{r.get('confidence')}/{r.get('knowledge')}] "
                            f"{r.get('claim','')} (src: {r.get('source','?')})"
                            for r in rows[:40])
        out = self.client.complete_json(
            self.system_prompt,
            f"Evidence rows:\n{summary}\n\n"
            'Return JSON: {"critiques": [{"issue": "...", "severity": "high|moderate|low"}]} '
            "with 2-6 concrete critiques.",
            default={"critiques": []})
        if out.get("_unavailable"):
            unavailable.append("LLM (red-team critique)")
        sev_conf = {"high": Confidence.HIGH, "moderate": Confidence.MODERATE, "low": Confidence.LOW}
        for c in out.get("critiques", []):
            evidence.append(Evidence(
                claim="Red-team critique: " + c.get("issue", "").strip(),
                source="red_team:independent-review",
                confidence=sev_conf.get(c.get("severity", "moderate"), Confidence.MODERATE),
                knowledge=Knowledge.IMPLEMENTED, agent=self.name))

        status = "degraded" if unavailable else "done"
        return AgentResult(
            agent=self.name, status=status, evidence=evidence,
            notes=f"{len(evidence)} critique(s) raised",
            payload={"critique_count": len(evidence)}, sources_unavailable=unavailable)
