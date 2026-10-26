"""Shared data structures passed between agents as clean JSON.

Knowledge-category tag is attached to every claim per the Navigator discipline:
every Evidence row says whether it is an Idea, a Design, an Implementation, a Verified
fact — or explicitly UNKNOWN. The system must be able to say when it does not know.
"""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Knowledge(str, Enum):
    IDEA = "idea"
    DESIGNED = "designed"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    UNKNOWN = "unknown"  # the system must be able to say it does not know


class Confidence(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNCERTAIN = "uncertain"


class Variant(BaseModel):
    gene: str | None = None
    hgvs: str | None = None          # language-independent identifier for cross-lingual search
    chrom: str | None = None
    pos: int | None = None
    ref: str | None = None
    alt: str | None = None
    rsid: str | None = None
    allele_freq: float | None = None  # from VCF INFO (AF) or case, used by Filtering
    raw: dict[str, Any] = Field(default_factory=dict)

    def short(self) -> str:
        if self.gene and self.hgvs:
            return f"{self.gene} {self.hgvs}"
        if self.gene:
            return self.gene
        if self.chrom and self.pos:
            return f"{self.chrom}:{self.pos}{self.ref or ''}>{self.alt or ''}"
        return "unknown-variant"


class Evidence(BaseModel):
    """One piece of evidence with its source and uncertainty label."""
    claim: str
    source: str                       # link/citation back to the origin (never unsourced)
    confidence: Confidence = Confidence.UNCERTAIN
    knowledge: Knowledge = Knowledge.UNKNOWN
    agent: str = ""
    gene: str | None = None           # variant/gene this evidence bears on (for grouping)


class Finding(BaseModel):
    """A ranked candidate the dossier presents as a hypothesis (never a diagnosis)."""
    rank: int
    gene: str | None = None
    variant: str | None = None
    rationale: str = ""
    confidence: Confidence = Confidence.UNCERTAIN
    supporting: list[str] = Field(default_factory=list)      # evidence claims for
    contradicting: list[str] = Field(default_factory=list)   # evidence claims against
    uncertainty: str = ""             # explicit uncertainty label / caveats


class CaseInput(BaseModel):
    case_id: str
    variants: list[Variant] = Field(default_factory=list)
    clinical_summary: str = ""
    hpo_terms: list[str] = Field(default_factory=list)
    vcf_path: str | None = None


class AgentResult(BaseModel):
    agent: str
    status: str = "done"              # idle | working | done | error | degraded
    evidence: list[Evidence] = Field(default_factory=list)
    notes: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    elapsed_s: float = 0.0
    sources_unavailable: list[str] = Field(default_factory=list)
