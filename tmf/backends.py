from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from .extract import ApiNode, ClassNode, ConfigNode, DeclarationNode, FunctionNode

ExtractionTier = Literal["python-ast", "java-treesitter-syntactic", "semantic-resolved"]


@dataclass(frozen=True)
class ExtractionResult:
    functions: list[FunctionNode]
    classes: list[ClassNode]
    declarations: list[DeclarationNode]
    configs: list[ConfigNode]
    apis: list[ApiNode]
    tier: ExtractionTier | None
    degraded: bool = False
    degrade_hint: str | None = None


class ExtractorBackend(ABC):
    tier: ExtractionTier

    @abstractmethod
    def supports_path(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def extract(self, path: str, source: str) -> ExtractionResult:
        raise NotImplementedError


class SemanticExtractorBackend(ABC):
    """Future semantic read-through/background backend interface.

    Step0 intentionally does not implement SCIP/LSP/semantic extraction. A future
    backend can run in the background, publish stronger semantic claims, and
    degrade to syntactic/source read-through when unavailable.
    """

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def enqueue_background_refresh(self, repo_root: str, path: str) -> None:
        raise NotImplementedError


class SemanticBackendUnavailable(SemanticExtractorBackend):
    def available(self) -> bool:
        return False

    def enqueue_background_refresh(self, repo_root: str, path: str) -> None:
        return None
