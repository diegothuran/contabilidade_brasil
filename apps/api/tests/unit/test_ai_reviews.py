from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from contabil.ai_reviews.model import (
    MAX_POINTS,
    AnthropicReviewClient,
    FakeReviewClient,
    ReviewAnswer,
    ReviewCallError,
    ReviewPoint,
    build_review_prompt,
    read_review,
    validate_points,
)
from contabil.ai_reviews.packet import PENDING_KEYS, AccountLine, compose_packet, packet_refs, packet_sha256
from contabil.ai_reviews.service import _COUNT_KEYS


def _line(code: str, kind: str, closing: str, previous=(None, None, None), **extra) -> AccountLine:
    return AccountLine(
        code=code,
        name=f"Conta {code}",
        account_type=kind,
        opening=Decimal(extra.get("opening", "0")),
        debit=Decimal(extra.get("debit", "0")),
        credit=Decimal(extra.get("credit", "0")),
        closing=Decimal(closing),
        previous_moves=tuple(None if value is None else Decimal(value) for value in previous),
    )


def _packet() -> dict:
    return compose_packet(
        competence="2026-11",
        period_status="open",
        accounts=[
            _line("1.1.02", "asset", "1500.00", ("100.00", None, "-50.00"), debit="2000.00", credit="500.00"),
            _line("5.1.01", "expense", "500.00", ("120.00", "130.00", "125.00"), debit="500.00"),
            _line("9.9.99", "expense", "0", debit="0"),
        ],
        indicators={
            "receita": ("2000.00", ["1000.00", None, "1100.00"]),
            "despesa": ("500.00", ["120.00", "130.00", "125.00"]),
            "resultado": ("1500.00", ["880.00", None, "975.00"]),
            "dinheiro_em_conta": ("1500.00", []),
        },
        checks=[{"kind": "idle_balance", "code": "5.1.01", "amount": "500.00"}],
        pending={"lancamentos_rascunho": 2, "casos_conciliacao_pendentes": 0},
    )


def test_packet_drops_empty_accounts_and_keeps_strings():
    packet = _packet()
    codes = [item["codigo"] for item in packet["contas"]]
    assert codes == ["1.1.02", "5.1.01"]
    bank = packet["contas"][0]
    assert bank["saldo_atual"] == "1500.00"
    assert bank["movimento_meses_anteriores"] == ["100.00", None, "-50.00"]
    assert packet["conferencias"] == [{"id": "c1", "tipo": "idle_balance", "conta": "5.1.01", "valor": "500.00"}]
    assert packet["indicadores"]["receita"] == {"mes": "2000.00", "meses_anteriores": ["1000.00", None, "1100.00"]}


def test_packet_has_no_entity_identity():
    text = json.dumps(_packet(), ensure_ascii=False)
    for forbidden in ("cnpj", "legal_entity", "tenant", "razao_social", "nome_empresa"):
        assert forbidden not in text.lower()


def test_packet_hash_is_stable_and_sensitive():
    assert packet_sha256(_packet()) == packet_sha256(_packet())
    changed = _packet()
    changed["contas"][0]["saldo_atual"] = "1500.01"
    assert packet_sha256(changed) != packet_sha256(_packet())


def test_refs_cover_every_fact_kind():
    refs = packet_refs(_packet())
    assert {"conta:1.1.02", "conta:5.1.01", "conferencia:c1", "indicador:receita", "pendencia:lancamentos_rascunho"} <= refs
    assert "conta:9.9.99" not in refs


def _point(**overrides) -> ReviewPoint:
    values = {
        "relevancia": "alta",
        "categoria": "variacao",
        "titulo": "Receita subiu muito",
        "explicacao": "A receita dobrou em relação aos meses anteriores.",
        "evidencias": ["indicador:receita"],
    }
    values.update(overrides)
    return ReviewPoint(**values)


def test_validate_drops_points_without_valid_evidence():
    refs = packet_refs(_packet())
    answer = ReviewAnswer(
        pontos=[
            _point(),
            _point(titulo="Inventado", evidencias=["conta:7.7.77", "nota:1"]),
            _point(titulo="Misto", evidencias=["conta:7.7.77", "conta:5.1.01"]),
        ]
    )
    points = validate_points(answer, refs)
    assert [(point.title, point.evidence) for point in points] == [
        ("Receita subiu muito", ["indicador:receita"]),
        ("Misto", ["conta:5.1.01"]),
    ]


def test_validate_coerces_enums_trims_and_limits():
    refs = packet_refs(_packet())
    answer = ReviewAnswer(
        pontos=[_point(relevancia="crítica", categoria="fraude", titulo="T" * 300, explicacao="E" * 900)]
        + [_point(titulo=f"Ponto {index}") for index in range(MAX_POINTS + 3)]
    )
    points = validate_points(answer, refs)
    assert len(points) == MAX_POINTS
    first = points[0]
    assert (first.relevance, first.category, len(first.title), len(first.explanation)) == ("baixa", "outro", 120, 600)


def test_validate_skips_repeated_titles():
    refs = packet_refs(_packet())
    answer = ReviewAnswer(pontos=[_point(), _point(explicacao="Outra explicação")])
    assert len(validate_points(answer, refs)) == 1


def test_prompt_carries_packet_and_guardrails():
    system, user = build_review_prompt(_packet())
    assert "não é um lançamento" in system.lower() or "não altera" in system.lower()
    assert "conferencias" in system or "conferências" in system
    assert json.loads(user)["competencia"] == "2026-11"


def test_read_review_only_accepts_end_turn_json():
    good = json.dumps({"pontos": [_point().model_dump()]})
    assert read_review("end_turn", good, 10, 5).answer is not None
    broken = read_review("end_turn", good[:20], 10, 5)
    assert (broken.answer, broken.stop_reason, broken.input_tokens) == (None, "invalid_output", 10)
    refused = read_review("refusal", "", 7, 0)
    assert (refused.answer, refused.stop_reason) == (None, "refusal")


def test_fake_client_answers_with_given_points():
    client = FakeReviewClient([_point()])
    result = client.review(system="s", user=json.dumps(_packet()))
    assert result.answer is not None and result.answer.pontos[0].titulo == "Receita subiu muito"
    assert client.calls == 1


def test_anthropic_client_uses_fallbacks_and_structured_output():
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        text = json.dumps({"pontos": []})
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        )

    sdk = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    result = AnthropicReviewClient("chave", "claude-opus-5-5", sdk=sdk).review(system="s", user="u")
    assert result.answer == ReviewAnswer(pontos=[])
    call = calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"]["effort"] == "high"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in call


def test_anthropic_client_hides_content_in_errors():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def create(**kwargs):
        del kwargs
        raise anthropic.APIConnectionError(request=request)

    sdk = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    with pytest.raises(ReviewCallError, match="APIConnectionError"):
        AnthropicReviewClient("chave", "claude-opus-5-5", sdk=sdk).review(system="segredo", user="segredo")


def test_every_pending_key_has_a_checklist_count():
    assert set(_COUNT_KEYS) == set(PENDING_KEYS)
