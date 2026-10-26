"""Base class for every agent. Each agent runs in its own private context.

Status: SCAFFOLD (Designed). Prompt scaffolding is in place; outputs are NOT verified.
"""
from __future__ import annotations
from abc import ABC, abstractmethod

from src.models.meta_client import MetaModelClient
from src.utils.schema import CaseInput, AgentResult


class BaseAgent(ABC):
    name: str = "base"
    model: str = "muse-spark"

    def __init__(self, model: str | None = None):
        if model:
            self.model = model
        self.client = MetaModelClient(self.model)

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The agent's focused, private instructions."""
        ...

    @abstractmethod
    def run(self, case: CaseInput, context: dict) -> AgentResult:
        """Do this agent's one job and return structured evidence.

        `context` holds only the clean, structured outputs this agent needs —
        never the entire shared history.
        """
        ...
