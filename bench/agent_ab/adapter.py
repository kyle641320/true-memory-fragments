from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AgentAdapter(ABC):
    """Interface for real agent A/B runs in a user's environment.

    Offline CI must use scripted strategies only. Concrete adapters may wrap
    Claude Code, an API client, or another coding agent, but should record calls,
    read bytes, prompts, and outputs without changing tasks or metrics after
    seeing results.
    """

    @abstractmethod
    def answer(self, question: str, *, budget: int) -> dict[str, Any]:
        raise NotImplementedError


class StubAgentAdapter(AgentAdapter):
    def answer(self, question: str, *, budget: int) -> dict[str, Any]:
        return {"question": question, "budget": budget, "calls": 0, "read_bytes": 0, "answer": "stub: no LLM calls in offline benchmark"}
