from __future__ import annotations

from abc import ABC, abstractmethod

from ai_research_radar.schemas.models import CanonicalSignal, RawItem


class SourceError(RuntimeError):
    def __init__(self, source: str, error_type: str, message: str) -> None:
        self.source = source
        self.error_type = error_type
        super().__init__(message)


class SourceAdapter(ABC):
    source_name: str
    source_family: str
    collection_diagnostics: dict[str, object]

    @abstractmethod
    def collect(self, since: str, until: str) -> list[RawItem]:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, item: RawItem) -> CanonicalSignal:
        raise NotImplementedError
