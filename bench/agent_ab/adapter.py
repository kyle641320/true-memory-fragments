from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Any, Mapping, Sequence


class AgentAdapterError(RuntimeError):
    """Fail-closed error raised before a benchmark arm can be counted."""


class AgentAdapter(ABC):
    """Interface for real agent A/B runs in a user's environment.

    Offline CI must use scripted strategies only. Concrete adapters may wrap a
    coding agent or a narrow model broker, but must record calls, read bytes,
    prompts, and outputs without changing tasks or metrics after seeing results.
    """

    @abstractmethod
    def answer(self, question: str, *, budget: int) -> dict[str, Any]:
        raise NotImplementedError


class StubAgentAdapter(AgentAdapter):
    def answer(self, question: str, *, budget: int) -> dict[str, Any]:
        return {"question": question, "budget": budget, "calls": 0, "read_bytes": 0, "answer": "stub: no LLM calls in offline benchmark"}


@dataclass(frozen=True)
class BrokerPreflight:
    protocol: str
    model: str
    stateless: bool
    tools: tuple[str, ...]
    network_owner: str
    credential_owner: str

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "BrokerPreflight":
        try:
            result = cls(
                protocol=str(value["protocol"]),
                model=str(value["model"]),
                stateless=value["stateless"] is True,
                tools=tuple(value["tools"]),
                network_owner=str(value["network_owner"]),
                credential_owner=str(value["credential_owner"]),
            )
        except (KeyError, TypeError) as exc:
            raise AgentAdapterError("broker preflight response is incomplete") from exc
        if result.protocol != "tmf-agent-broker-v1":
            raise AgentAdapterError("unsupported broker protocol")
        if not result.model or not result.stateless:
            raise AgentAdapterError("broker must pin a model and guarantee stateless execution")
        if result.tools:
            raise AgentAdapterError("broker must expose raw inference only, never host tools")
        if result.network_owner != "broker" or result.credential_owner != "broker":
            raise AgentAdapterError("network and credentials must remain broker-owned")
        return result


class JsonBrokerAdapter(AgentAdapter):
    """Narrow raw-model adapter for an already-isolated arm runner.

    The executable is an explicit, owner-supplied broker.  It receives one JSON
    request on stdin and must return one JSON object on stdout.  The adapter
    never discovers OpenClaw state, forwards ambient credentials, enables host
    tools, or falls back to another execution path.  Repository/tool mediation
    remains the isolated runner's responsibility.
    """

    _ALLOWED_ENV = ("LANG", "LC_ALL", "TZ")

    def __init__(self, command: Sequence[str], *, expected_model: str, timeout_seconds: int = 120):
        if not command or not Path(command[0]).is_absolute():
            raise AgentAdapterError("broker executable must be an absolute path")
        executable = Path(command[0])
        try:
            mode = executable.stat().st_mode
        except OSError as exc:
            raise AgentAdapterError(f"broker executable is unavailable: {executable}") from exc
        if not stat.S_ISREG(mode) or not os.access(executable, os.X_OK):
            raise AgentAdapterError("broker executable must be an executable regular file")
        self.command = tuple(command)
        self.expected_model = expected_model
        self.timeout_seconds = timeout_seconds
        self._preflight: BrokerPreflight | None = None

    def _run(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        env = {key: os.environ[key] for key in self._ALLOWED_ENV if key in os.environ}
        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(request, separators=(",", ":")) + "\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AgentAdapterError("broker execution failed") from exc
        if completed.returncode != 0:
            raise AgentAdapterError(f"broker rejected request (exit {completed.returncode})")
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise AgentAdapterError("broker returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise AgentAdapterError("broker response must be a JSON object")
        return value

    def preflight(self) -> BrokerPreflight:
        result = BrokerPreflight.parse(self._run({"protocol": "tmf-agent-broker-v1", "op": "preflight"}))
        if result.model != self.expected_model:
            raise AgentAdapterError("broker model does not match the frozen manifest")
        self._preflight = result
        return result

    def answer(self, question: str, *, budget: int) -> dict[str, Any]:
        if self._preflight is None:
            raise AgentAdapterError("broker preflight is required before assignment")
        if not question.strip() or budget < 1:
            raise AgentAdapterError("question and positive budget are required")
        value = self._run({
            "protocol": "tmf-agent-broker-v1",
            "op": "complete",
            "model": self.expected_model,
            "prompt": question,
            "budget": budget,
        })
        if value.get("protocol") != "tmf-agent-broker-v1" or value.get("model") != self.expected_model:
            raise AgentAdapterError("broker completion violated the locked protocol/model")
        if not isinstance(value.get("answer"), str) or not value["answer"].strip():
            raise AgentAdapterError("broker completion has no answer")
        if not isinstance(value.get("calls"), int) or not 0 <= value["calls"] <= budget:
            raise AgentAdapterError("broker completion has invalid call telemetry")
        return dict(value)
