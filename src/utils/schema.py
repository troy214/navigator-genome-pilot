"""Shared data structures passed between agents as clean JSON.

Knowledge-category tag is attached to every claim per the Navigator discipline.
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
    raw: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """One piece of evidence with its source and uncertainty label."""
    claim: str
    source: str                       # link/citation back to the origin (never unsourced)
    confidence: Confidence = Confidence.UNCERTAIN
    knowledge: Knowledge = Knowledge.UNKNOWN
    agent: str = ""


class CaseInput(BaseModel):
    case_id: str
    variants: list[Variant] = Field(default_factory=list)
    clinical_summary: str = ""
    hpo_terms: list[str] = Field(default_factory=list)
    vcf_path: str | None = None


class AgentResult(BaseModel):
    agent: str
    evidence: list[Evidence] = Field(default_factory=list)
    notes: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
