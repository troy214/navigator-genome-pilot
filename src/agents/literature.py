"""Agent 4 — Literature. Search Europe PMC and summarize with citations.

Every summarized claim carries a citation (PMID/DOI/URL). No citation, no claim.
"""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.clients import europepmc
from src.utils.schema import CaseInput, AgentResult, Evidence, Variant, Confidence, Knowledge


class LiteratureAgent(BaseAgent):
    name = "literature"

    @property
    def system_prompt(self) -> str:
        return (
            "You summarize biomedical publications for a gene + variant + phenotype. You are given "
            "a list of real articles (title, citation). Summarize what the literature says about "
            "the gene's disease association. EVERY claim must reference one of the provided "
            "citations by its exact token. Never state a claim you cannot attach to a citation."
        )

    def _run(self, case: CaseInput, context: dict) -> AgentResult:
        variants = [Variant(**v) for v in context.get("filtering", {}).get("variants", [])]
        pheno = context.get("phenotype", {}).get("hpo_terms", [])
        pheno_text = ", ".join(t.get("name", "") for t in pheno[:5])

        evidence: list[Evidence] = []
        unavailable: list[str] = []
        genes = [v.gene for v in variants if v.gene] or []
        if not genes:
            return AgentResult(agent=self.name, status="done",
                               notes="no genes to search", payload={"articles": []})

        all_articles = []
        for gene in dict.fromkeys(genes):  # unique, order-preserving
            query = f'{gene} AND (variant OR mutation OR pathogenic)'
            if pheno_text:
                query = f'{gene} AND ({pheno_text.split(",")[0]})'
            hits = europepmc.search(query, page_size=4)
            if not hits:
                unavailable.append(f"Europe PMC (gene {gene})")
                continue
            all_articles.extend([{**h, "gene": gene} for h in hits])

        if not all_articles:
            return AgentResult(agent=self.name, status="degraded",
                               notes="no literature retrieved", payload={"articles": []},
                               sources_unavailable=unavailable or ["Europe PMC"])

        # Summarize with the LLM, constrained to the retrieved citations.
        cite_list = "\n".join(
            f"- [{a['citation']}] {a['title']} ({a.get('journal','')} {a.get('year','')})"
            for a in all_articles)
        out = self.client.complete_json(
            self.system_prompt,
            f"Gene(s): {', '.join(dict.fromkeys(genes))}\nPhenotype: {pheno_text}\n\n"
            f"Articles:\n{cite_list}\n\n"
            'Return JSON: {"claims": [{"claim": "...", "citation": "PMID:... or DOI:...", '
            '"gene": "..."}]} with 2-5 claims, each citation taken verbatim from the list above.',
            default={"claims": []})
        if out.get("_unavailable"):
            unavailable.append("LLM (literature summary)")

        valid_cites = {a["citation"] for a in all_articles}
        cite_url = {a["citation"]: a["url"] for a in all_articles}
        for c in out.get("claims", []):
            cite = c.get("citation", "")
            if cite in valid_cites:  # enforce: no citation, no claim
                evidence.append(Evidence(
                    claim=c.get("claim", "").strip(),
                    source=f"{cite} ({cite_url[cite]})",
                    confidence=Confidence.MODERATE, knowledge=Knowledge.VERIFIED,
                    agent=self.name, gene=c.get("gene")))

        status = "degraded" if unavailable else "done"
        return AgentResult(
            agent=self.name, status=status, evidence=evidence,
            notes=f"{len(all_articles)} article(s) retrieved, {len(evidence)} sourced claim(s)",
            payload={"articles": all_articles}, sources_unavailable=unavailable)
