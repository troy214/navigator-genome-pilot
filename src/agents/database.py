"""Agent 5 — Database. Query real variant/disease databases.

MyVariant.info (ClinVar/gnomAD/dbNSFP aggregate) + ClinVar E-utilities + gnomAD GraphQL.
Returns structured records with source + version. Distinguishes ABSENT from BENIGN.
Never fabricates an entry.
"""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.clients import myvariant, clinvar, gnomad
from src.utils.schema import CaseInput, AgentResult, Evidence, Variant, Confidence, Knowledge

_SIG_CONF = {
    "pathogenic": Confidence.HIGH,
    "likely pathogenic": Confidence.MODERATE,
    "benign": Confidence.HIGH,
    "likely benign": Confidence.MODERATE,
}


class DatabaseAgent(BaseAgent):
    name = "database"

    @property
    def system_prompt(self) -> str:
        return (
            "You query curated variant/disease databases and return structured records with "
            "source + version. Distinguish an absent record from a benign record. Never fabricate."
        )

    def _run(self, case: CaseInput, context: dict) -> AgentResult:
        variants = [Variant(**v) for v in context.get("filtering", {}).get("variants", [])]
        evidence: list[Evidence] = []
        unavailable: list[str] = []
        records: list[dict] = []

        for v in variants:
            if not v.gene:
                continue
            gene = v.gene

            # MyVariant.info aggregate (clinical significance + gnomAD AF)
            mv = myvariant.query_gene_variant(
                gene, "clinvar.rcv.clinical_significance:pathogenic", size=2)
            if not mv["available"]:
                unavailable.append(f"MyVariant.info ({gene})")
            else:
                for h in mv["hits"]:
                    sig = (h.get("clinical_significance") or "").lower()
                    conf = _SIG_CONF.get(sig, Confidence.UNCERTAIN)
                    af = h.get("gnomad_af")
                    af_txt = f"; gnomAD AF {af:.3g}" if isinstance(af, (int, float)) else ""
                    evidence.append(Evidence(
                        claim=f"{gene} {h.get('id','')}: ClinVar significance "
                              f"'{h.get('clinical_significance') or 'not reported'}'{af_txt}.",
                        source=mv["source"], confidence=conf,
                        knowledge=Knowledge.VERIFIED, agent=self.name, gene=gene))
                    records.append({"gene": gene, **h, "source": mv["source"]})

            # ClinVar E-utilities (absent vs benign discipline)
            cv = clinvar.query(gene, retmax=2)
            if not cv["available"]:
                unavailable.append(f"ClinVar ({gene})")
            elif not cv["present"]:
                evidence.append(Evidence(
                    claim=f"No ClinVar record found for {gene} with this query "
                          f"(absent — NOT evidence of benignity).",
                    source=cv["source"], confidence=Confidence.LOW,
                    knowledge=Knowledge.UNKNOWN, agent=self.name, gene=gene))
            else:
                for r in cv["records"][:2]:
                    sig = (r.get("clinical_significance") or "").lower()
                    evidence.append(Evidence(
                        claim=f"ClinVar {r.get('accession','')}: {r.get('title','')} — "
                              f"significance '{r.get('clinical_significance') or 'not reported'}' "
                              f"(last evaluated {r.get('last_evaluated') or 'n/a'}).",
                        source=f"{cv['source']} ({r.get('url','')})",
                        confidence=_SIG_CONF.get(sig, Confidence.UNCERTAIN),
                        knowledge=Knowledge.VERIFIED, agent=self.name, gene=gene))
                    records.append({"gene": gene, **r, "source": cv["source"]})

            # gnomAD gene-level confirmation
            gad = gnomad.gene_info(gene)
            if not gad["available"]:
                unavailable.append(f"gnomAD ({gene})")
            elif gad["gene"]:
                evidence.append(Evidence(
                    claim=f"{gene} confirmed in gnomAD ({gad['gene'].get('gene_id')}, "
                          f"{gad['gene'].get('name','')}).",
                    source=gad["source"], confidence=Confidence.HIGH,
                    knowledge=Knowledge.VERIFIED, agent=self.name, gene=gene))

        status = "degraded" if unavailable else "done"
        return AgentResult(
            agent=self.name, status=status, evidence=evidence,
            notes=f"{len(records)} database record(s); "
                  f"{len(set(unavailable))} source(s) unavailable",
            payload={"records": records}, sources_unavailable=sorted(set(unavailable)))
