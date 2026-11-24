"""Cliente do modelo para a revisão do mês (ADR 036).

O pacote do mês é a única entrada. A resposta é uma lista de pontos para conferência humana;
cada ponto precisa citar uma evidência que existe no pacote, ou é descartado.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

PROMPT_VERSION = "revisao-1"
MAX_TOKENS = 16000
EFFORT = "high"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_POINTS = 10
TITLE_LIMIT = 120
EXPLANATION_LIMIT = 600
INVALID_OUTPUT = "invalid_output"
INCOMPLETE_STOPS = frozenset({"refusal", "max_tokens", INVALID_OUTPUT})
RELEVANCES = ("alta", "média", "baixa")
CATEGORIES = ("variacao", "classificacao", "saldo", "coerencia", "pendencia", "outro")

SYSTEM_PROMPT = (
    "Você revisa o mês contábil de uma empresa para um escritório de contabilidade brasileiro. "
    "O JSON do usuário é o pacote do mês: balancete com saldo anterior, débito, crédito e saldo atual de cada conta, "
    "o movimento líquido (débito menos crédito) das três competências anteriores, indicadores da DRE, "
    "as conferências que o sistema já calculou e as contagens de pendência. "
    "Aponte o que um contador experiente olharia antes de fechar: variação fora do padrão entre meses, "
    "conta que não combina com o resto do balancete, resultado que não conversa com o dinheiro em conta, "
    "pendência que compromete os números. "
    "As conferências do pacote já aparecem para o contador: só as cite quando acrescentar uma explicação ou uma ligação "
    "com outro número. Não repita o que o pacote já diz. "
    "A relevância é \"alta\", \"média\" ou \"baixa\". A categoria é uma destas: \"variacao\" (mudança fora do padrão entre meses), "
    "\"classificacao\" (valor que parece estar na conta errada), \"saldo\" (saldo estranho para a natureza ou a idade da conta), "
    "\"coerencia\" (números que não conversam entre si, como resultado e caixa), \"pendencia\" (pendência que compromete os números) "
    "ou \"outro\". "
    "Cada ponto cita pelo menos uma evidência no formato conta:<código>, conferencia:<id>, indicador:<chave> "
    "ou pendencia:<chave>, usando só o que está no pacote. Não invente número, conta ou fato fora do pacote. "
    "Sua resposta não altera o razão: é uma sugestão que o contador confere e decide. "
    "Escreva em português, com frases curtas, sem jargão desnecessário. Se nada merece atenção, devolva a lista vazia. "
    f"No máximo {MAX_POINTS} pontos, do mais relevante ao menos relevante."
)


class ReviewPoint(BaseModel):
    relevancia: str
    categoria: str
    titulo: str
    explicacao: str
    evidencias: list[str]


class ReviewAnswer(BaseModel):
    pontos: list[ReviewPoint]


@dataclass
class ReviewResult:
    answer: ReviewAnswer | None
    stop_reason: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ValidPoint:
    relevance: str
    category: str
    title: str
    explanation: str
    evidence: list[str]


class ReviewClient(Protocol):
    def review(self, *, system: str, user: str) -> ReviewResult: ...


class ReviewCallError(RuntimeError):
    """Falha na chamada. A mensagem leva só o tipo do erro, nunca o pacote enviado."""


def answer_schema() -> dict:
    import anthropic

    return anthropic.transform_schema(ReviewAnswer)


class AnthropicReviewClient:
    def __init__(self, api_key: str, model: str, *, sdk: Any | None = None) -> None:
        if sdk is None:
            import anthropic

            sdk = anthropic.Anthropic(api_key=api_key, timeout=120, max_retries=2)
        self._sdk = sdk
        self.model = model

    def review(self, *, system: str, user: str) -> ReviewResult:
        import anthropic

        try:
            response = self._sdk.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": answer_schema()}},
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIError as exc:
            raise ReviewCallError(f"falha na chamada ao modelo: {exc.__class__.__name__}") from None
        usage = getattr(response, "usage", None)
        text = "".join(
            getattr(block, "text", "") for block in (getattr(response, "content", None) or []) if getattr(block, "type", "") == "text"
        )
        return read_review(
            str(getattr(response, "stop_reason", "") or ""),
            text,
            int(getattr(usage, "input_tokens", 0) or 0),
            int(getattr(usage, "output_tokens", 0) or 0),
        )


def read_review(stop_reason: str, text: str, input_tokens: int, output_tokens: int) -> ReviewResult:
    answer: ReviewAnswer | None = None
    if stop_reason == "end_turn":
        try:
            answer = ReviewAnswer.model_validate_json(text)
        except ValidationError:
            stop_reason = INVALID_OUTPUT
    return ReviewResult(answer=answer, stop_reason=stop_reason, input_tokens=input_tokens, output_tokens=output_tokens)


class FakeReviewClient:
    """Cliente determinístico para teste, pelo mesmo caminho de leitura do cliente real."""

    def __init__(self, points: Sequence[ReviewPoint], *, stop_reason: str = "end_turn", fail: bool = False) -> None:
        self.points = list(points)
        self.stop_reason = stop_reason
        self.fail = fail
        self.calls = 0
        self.last_user: str | None = None

    def review(self, *, system: str, user: str) -> ReviewResult:
        del system
        self.calls += 1
        self.last_user = user
        if self.fail:
            raise ReviewCallError("falha na chamada ao modelo: APIConnectionError")
        text = json.dumps({"pontos": [point.model_dump() for point in self.points]}, ensure_ascii=False)
        if self.stop_reason != "end_turn":
            text = text[: len(text) // 2]
        return read_review(self.stop_reason, text, 1000, 200)


def build_review_prompt(packet: Mapping) -> tuple[str, str]:
    return SYSTEM_PROMPT, json.dumps(packet, ensure_ascii=False, sort_keys=True)


def validate_points(answer: ReviewAnswer, refs: set[str]) -> list[ValidPoint]:
    """Pontos aproveitáveis, na ordem da resposta. Nada aqui levanta erro."""
    points: list[ValidPoint] = []
    seen: set[str] = set()
    for point in answer.pontos:
        evidence = list(dict.fromkeys(ref.strip() for ref in point.evidencias if ref.strip() in refs))
        title = " ".join(point.titulo.split())[:TITLE_LIMIT]
        if not evidence or not title or title.casefold() in seen:
            continue
        seen.add(title.casefold())
        points.append(
            ValidPoint(
                relevance=point.relevancia if point.relevancia in RELEVANCES else "baixa",
                category=point.categoria if point.categoria in CATEGORIES else "outro",
                title=title,
                explanation=point.explicacao.strip()[:EXPLANATION_LIMIT],
                evidence=evidence,
            )
        )
        if len(points) == MAX_POINTS:
            break
    return points
