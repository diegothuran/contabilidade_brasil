from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Confidence = Literal["alta", "média", "baixa"]
Source = Literal["history", "model"]
CONFIDENCES: tuple[str, ...] = ("alta", "média", "baixa")


@dataclass(frozen=True)
class Suggestion:
    """Conta sugerida para a contrapartida. É sempre sugestão: a pessoa confirma (ADR 004)."""

    account_id: str
    code: str
    name: str
    confidence: Confidence
    justification: str
    source: Source
    provider_version: str


def suggestion_dict(suggestion: Suggestion) -> dict:
    return {
        "account_id": suggestion.account_id,
        "code": suggestion.code,
        "name": suggestion.name,
        "confidence": suggestion.confidence,
        "justification": suggestion.justification,
        "source": suggestion.source,
        "provider_version": suggestion.provider_version,
    }
