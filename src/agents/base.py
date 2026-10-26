"""Base class for every agent. Each agent runs in its own private context.

An agent receives only the clean, structured context it needs — never the whole shared
history. Every agent returns an AgentResult carrying Evidence rows, each with a source
and an explicit uncertainty + knowledge-category label.
"""
from __future__ import annotations
import time
from abc import ABC, abstractmethod

from src.models.meta_client import MetaModelClient
from src.models.config import model_for
from src.utils.schema import CaseInput, AgentResult


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, model: str | None = None):
        # Model name is resolved from the ACTIVE provider (dev vs Meta) — no hardcoding.
        self.model = model or model_for(self.name)
        self.client = MetaModelClient(self.model)

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The agent's focused, private instructions."""
        ...

    @abstractmethod
    def _run(self, case: CaseInput, context: dict) -> AgentResult:
        """Subclass implementation. Wrapped by run() for timing + error safety."""
        ...

    def run(self, case: CaseInput, context: dict) -> AgentResult:
        """Public entry: times the agent and guarantees a result (never crashes the pipeline)."""
        t0 = time.time()
        try:
            res = self._run(case, context)
        except Exception as e:  # noqa: BLE001
            res = AgentResult(agent=self.name, status="error",
                              notes=f"agent error: {type(e).__name__}: {e}")
        res.elapsed_s = round(time.time() - t0, 3)
        if res.status == "idle":
            res.status = "done"
        return res
