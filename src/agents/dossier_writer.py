"""Agent 8 — Dossier Writer. Assemble the physician-facing evidence dossier + render PDF.

Ranking is deterministic (traceable); the per-finding rationale narrative uses the LLM.
Output: a structured dossier dict + a rendered PDF in data/ (S3 destination documented).
"""
from __future__ import annotations
from pathlib import Path

from config import settings
from src.agents.base import BaseAgent
from src.pipeline.dossier_pdf import render_dossier
from src.utils.schema import (
    CaseInput, AgentResult, Evidence, Finding, Variant, Confidence, Knowledge)

_CONF_WEIGHT = {"high": 3, "moderate": 2, "low": 1, "uncertain": 0}


class DossierWriterAgent(BaseAgent):
    name = "dossier_writer"

    @property
    def system_prompt(self) -> str:
        return (
            "You write a concise, neutral rationale for a candidate genetic finding, citing only "
            "the supplied evidence. This is research decision SUPPORT, not a diagnosis. State "
            "uncertainty plainly. Never assert pathogenicity as established fact."
        )

    def _rank(self, variants, all_evidence, matches):
        # Score each candidate gene by weighted supporting evidence.
        genes = {}
        for v in variants:
            if v.gene:
                genes.setdefault(v.gene, {"variant": v.hgvs or v.short(), "support": 0.0,
                                          "supporting": [], "contradicting": []})
        # Fold in case-match genes too.
        for m in matches:
            genes.setdefault(m["gene"], {"variant": m.get("variant"), "support": 0.0,
                                         "supporting": [], "contradicting": []})

        for e in all_evidence:
            g = e.get("gene")
            if not g or g not in genes:
                continue
            w = _CONF_WEIGHT.get(e.get("confidence", "uncertain"), 0)
            claim = e.get("claim", "")
            low = claim.lower()
            contra = ("no clinvar record" in low or "benign" in low or "overstated" in low
                      or "absent" in low or "could not map" in low)
            if contra:
                genes[g]["contradicting"].append(f"{claim} [{e.get('source','')}]")
                genes[g]["support"] -= 0.5
            else:
                genes[g]["supporting"].append(f"{claim} [{e.get('source','')}]")
                genes[g]["support"] += w

        ranked = sorted(genes.items(), key=lambda kv: kv[1]["support"], reverse=True)
        findings = []
        for i, (gene, d) in enumerate(ranked, 1):
            score = d["support"]
            conf = (Confidence.MODERATE if score >= 5 else
                    Confidence.LOW if score >= 2 else Confidence.UNCERTAIN)
            findings.append(Finding(
                rank=i, gene=gene, variant=d["variant"], confidence=conf,
                supporting=d["supporting"][:6], contradicting=d["contradicting"][:6],
                uncertainty="Hypothesis only — requires expert review and orthogonal confirmation."))
        return findings

    def _run(self, case: CaseInput, context: dict) -> AgentResult:
        variants = [Variant(**v) for v in context.get("filtering", {}).get("variants", [])] \
            or list(case.variants)
        all_evidence = context.get("all_evidence", [])
        matches = context.get("case_matching", {}).get("matches", [])
        red_team = [e.get("claim", "") for e in all_evidence if e.get("agent") == "red_team"]
        hpo = context.get("phenotype", {}).get("hpo_terms", [])
        unavailable = sorted(set(context.get("sources_unavailable", [])))

        findings = self._rank(variants, all_evidence, matches)

        # LLM narrative rationale for the top findings (graceful if unavailable).
        for f in findings[:3]:
            support_txt = "\n".join(f.supporting) or "none"
            out = self.client.complete_json(
                self.system_prompt,
                f"Candidate gene: {f.gene} ({f.variant}).\nSupporting evidence:\n{support_txt}\n"
                f"Contradicting:\n{chr(10).join(f.contradicting) or 'none'}\n\n"
                'Return JSON: {"rationale": "2-3 neutral sentences citing the evidence"}.',
                default={"rationale": ""})
            f.rationale = out.get("rationale", "") or (
                f"{f.gene}: ranked on {len(f.supporting)} supporting evidence row(s).")

        dossier = {
            "case_id": case.case_id,
            "provider": settings.active_provider()["name"],
            "clinical_summary": case.clinical_summary,
            "hpo_terms": hpo,
            "findings": [f.model_dump(mode="json") for f in findings],
            "red_team": red_team,
            "sources_unavailable": unavailable,
            "evidence": all_evidence,
        }

        pdf_name = f"dossier_{case.case_id}.pdf"
        pdf_path = settings.DATA_DIR / pdf_name
        try:
            render_dossier(dossier, pdf_path)
            pdf_status = str(pdf_path)
        except Exception as e:  # noqa: BLE001
            pdf_status = f"PDF render failed: {type(e).__name__}: {e}"

        s3_dest = (f"s3://{settings.AWS_S3_BUCKET}/{settings.AWS_S3_DOSSIER_PREFIX}{pdf_name}"
                   if settings.AWS_S3_BUCKET else
                   f"(configure AWS_S3_BUCKET) {settings.AWS_S3_DOSSIER_PREFIX}{pdf_name}")

        evidence = [Evidence(
            claim=f"Assembled dossier with {len(findings)} ranked candidate finding(s); "
                  f"top candidate: {findings[0].gene if findings else 'none'}.",
            source="dossier_writer", confidence=Confidence.MODERATE,
            knowledge=Knowledge.IMPLEMENTED, agent=self.name)]

        return AgentResult(
            agent=self.name, status="done", evidence=evidence,
            notes=f"dossier -> {pdf_status}",
            payload={"dossier": dossier, "pdf_path": pdf_status, "s3_destination": s3_dest})
