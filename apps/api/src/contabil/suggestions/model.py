"""Cliente do modelo de linguagem para a sugestão de contrapartida (ADR 035).

O que sai: plano da empresa (código, nome, tipo), direção, faixa de valor e descrição
pseudonimizada, com um id local por transação. Valor exato, data, CNPJ, nome da empresa e
ids internos não saem. A resposta é validada contra o plano e vira sugestão, nunca lançamento.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel

from contabil.suggestions.pseudonymize import pseudonymize
from contabil.suggestions.types import CONFIDENCES

PROMPT_VERSION = "contrapartida-1"
BATCH_SIZE = 40
MAX_TOKENS = 4096
JUSTIFICATION_LIMIT = 300
_STOPS_WITHOUT_ANSWER = frozenset({"refusal", "max_tokens"})
_DIRECTIONS = {"inflow": "entrada", "outflow": "saída"}

SYSTEM_PROMPT = (
    "Você ajuda um escritório de contabilidade brasileiro a conciliar extratos bancários. "
    "Para cada transação, sugira a conta de contrapartida no plano de contas dado. "
    "A sua resposta é uma sugestão para conferência humana: um contador confere e decide antes de qualquer lançamento. "
    "Use só códigos que estão no plano dado; se nenhuma conta servir, não responda para aquela transação. "
    "A confiança é \"alta\", \"média\" ou \"baixa\". "
    "A justificativa tem uma frase curta, em português, sem repetir dados da descrição. "
    "Marcadores como [PESSOA], [CPF] e [CNPJ] substituem dados pessoais; não tente adivinhá-los."
)


class ModelPick(BaseModel):
    transaction_ref: str
    account_code: str
    confidence: str
    justification: str


class ModelAnswer(BaseModel):
    picks: list[ModelPick]


@dataclass
class ModelResult:
    answer: ModelAnswer | None
    stop_reason: str
    input_tokens: int
    output_tokens: int


class ModelClient(Protocol):
    def suggest(self, *, system: str, user: str) -> ModelResult: ...


class ModelCallError(RuntimeError):
    """Falha na chamada ao modelo. A mensagem leva só o tipo do erro, nunca o conteúdo enviado."""


class AnthropicModelClient:
    def __init__(self, api_key: str, model: str, *, sdk: Any | None = None) -> None:
        if sdk is None:
            import anthropic

            sdk = anthropic.Anthropic(api_key=api_key, timeout=30, max_retries=2)
        self._sdk = sdk
        self.model = model

    def suggest(self, *, system: str, user: str) -> ModelResult:
        import anthropic

        try:
            response = self._sdk.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                output_config={"effort": "low"},
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=ModelAnswer,
            )
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise ModelCallError(f"falha na chamada ao modelo: {exc.__class__.__name__}") from None
        stop_reason = str(response.stop_reason or "")
        usage = response.usage
        answer = None if stop_reason in _STOPS_WITHOUT_ANSWER else response.parsed_output
        return ModelResult(
            answer=answer,
            stop_reason=stop_reason,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )


class FakeModelClient:
    """Cliente determinístico para teste: responde (código, confiança) para os refs conhecidos do lote."""

    def __init__(self, picks_by_ref: dict[str, tuple[str, str]]) -> None:
        self.picks_by_ref = picks_by_ref
        self.calls = 0
        self.sizes: list[int] = []

    def suggest(self, *, system: str, user: str) -> ModelResult:
        del system
        self.calls += 1
        refs = [item["ref"] for item in json.loads(user)["transacoes"]]
        self.sizes.append(len(refs))
        picks = [
            ModelPick(transaction_ref=ref, account_code=code, confidence=confidence, justification="Sugestão de teste")
            for ref in refs
            if ref in self.picks_by_ref
            for code, confidence in [self.picks_by_ref[ref]]
        ]
        return ModelResult(answer=ModelAnswer(picks=picks), stop_reason="end_turn", input_tokens=100, output_tokens=20)


def value_band(amount: Decimal) -> str:
    value = abs(Decimal(amount))
    if value <= Decimal("100"):
        return "até 100"
    if value <= Decimal("1000"):
        return "100 a 1.000"
    if value <= Decimal("10000"):
        return "1.000 a 10.000"
    return "acima de 10.000"


def build_prompt(chart: Sequence[tuple[str, str, str]], txs: Sequence[tuple[str, str, str, str]]) -> tuple[str, str]:
    """`chart`: (código, nome, tipo). `txs`: (ref, direção, valor, descrição original).

    Valor vira faixa e descrição passa por `pseudonymize` aqui, para não haver caminho sem máscara.
    """
    body = {
        "plano_de_contas": [{"codigo": code, "nome": name, "tipo": kind} for code, name, kind in chart],
        "transacoes": [
            {
                "ref": ref,
                "direcao": _DIRECTIONS.get(direction, direction),
                "faixa_de_valor": value_band(Decimal(amount)),
                "descricao": pseudonymize(description),
            }
            for ref, direction, amount, description in txs
        ],
    }
    return SYSTEM_PROMPT, json.dumps(body, ensure_ascii=False)


def validate_picks(
    answer: ModelAnswer,
    refs: Mapping[str, str],
    accounts_by_code: Mapping[str, Any],
) -> list[tuple[str, Any, str, str]]:
    """(case_id, conta, confiança, justificativa) dos picks aproveitáveis; o resto é descartado sem erro."""
    picks: list[tuple[str, Any, str, str]] = []
    seen: set[str] = set()
    for pick in answer.picks:
        case_id = refs.get(pick.transaction_ref)
        account = accounts_by_code.get(pick.account_code)
        if case_id is None or case_id in seen or account is None:
            continue
        if not account.active or not account.postable:
            continue
        confidence = pick.confidence if pick.confidence in CONFIDENCES else "baixa"
        justification = (pick.justification or "").strip()[:JUSTIFICATION_LIMIT]
        seen.add(case_id)
        picks.append((case_id, account, confidence, justification))
    return picks
