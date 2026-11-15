from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from contabil.suggestions.model import (
    AnthropicModelClient,
    FakeModelClient,
    ModelAnswer,
    ModelCallError,
    ModelPick,
    build_prompt,
    validate_picks,
    value_band,
)


def _account(code: str, *, active: bool = True, postable: bool = True) -> SimpleNamespace:
    return SimpleNamespace(id=f"acc-{code}", code=code, name=f"Conta {code}", active=active, postable=postable)


def _cpf(base: str) -> str:
    digits = [int(char) for char in base]
    for size in (9, 10):
        total = sum(value * weight for value, weight in zip(digits, range(size + 1, 1, -1)))
        rest = (total * 10) % 11
        digits.append(0 if rest == 10 else rest)
    return "".join(str(value) for value in digits)


def test_validate_discards_unknown_and_inactive():
    accounts = {
        "5.1.01": _account("5.1.01"),
        "5.1.02": _account("5.1.02", active=False),
        "5": _account("5", postable=False),
    }
    answer = ModelAnswer(
        picks=[
            ModelPick(transaction_ref="t1", account_code="5.1.01", confidence="alta", justification="Tarifa"),
            ModelPick(transaction_ref="t9", account_code="5.1.01", confidence="alta", justification="Ref inventada"),
            ModelPick(transaction_ref="t2", account_code="9.9.99", confidence="média", justification="Conta inexistente"),
            ModelPick(transaction_ref="t2", account_code="5.1.02", confidence="média", justification="Inativa"),
            ModelPick(transaction_ref="t3", account_code="5", confidence="baixa", justification="Sintética"),
        ]
    )
    refs = {"t1": "case_1", "t2": "case_2", "t3": "case_3"}
    picks = validate_picks(answer, refs, accounts)
    assert [(case_id, account.code, confidence) for case_id, account, confidence, _ in picks] == [("case_1", "5.1.01", "alta")]


def test_validate_coerces_confidence_and_truncates():
    accounts = {"5.1.01": _account("5.1.01")}
    answer = ModelAnswer(
        picks=[
            ModelPick(transaction_ref="t1", account_code="5.1.01", confidence="certeza", justification="x" * 500),
            ModelPick(transaction_ref="t1", account_code="5.1.01", confidence="alta", justification="repetida"),
        ]
    )
    picks = validate_picks(answer, {"t1": "case_1"}, accounts)
    assert len(picks) == 1
    _case_id, _account_row, confidence, justification = picks[0]
    assert confidence == "baixa"
    assert len(justification) == 300


def test_prompt_has_no_raw_digits_or_names():
    cpf = _cpf("418273650")
    chart = [("5.1.01", "Despesas de serviços", "expense"), ("2.1.01", "Fornecedores", "liability")]
    txs = [
        ("t1", "outflow", "1500.00", f"PIX ENVIADO PARA JOAQUIM PEREIRA {cpf}"),
        ("t2", "inflow", "80.00", "TED RECEBIDO DE BEATRIZ NUNES"),
    ]
    system, user = build_prompt(chart, txs)
    assert cpf not in user
    assert "JOAQUIM" not in user and "PEREIRA" not in user and "BEATRIZ" not in user
    assert "1500" not in user
    assert "[CPF]" in user and "[PESSOA]" in user
    assert "1.000 a 10.000" in user and "até 100" in user
    assert "5.1.01" in user and "t1" in user
    assert "conferência humana" in system
    assert "alta" in system and "média" in system and "baixa" in system


def test_value_bands():
    assert value_band(Decimal("0.01")) == "até 100"
    assert value_band(Decimal("100.00")) == "até 100"
    assert value_band(Decimal("100.01")) == "100 a 1.000"
    assert value_band(Decimal("1000.00")) == "100 a 1.000"
    assert value_band(Decimal("1000.01")) == "1.000 a 10.000"
    assert value_band(Decimal("10000.00")) == "1.000 a 10.000"
    assert value_band(Decimal("10000.01")) == "acima de 10.000"


class _FakeMessages:
    """Imita `messages.create` da SDK: devolve blocos de texto, stop_reason e usage."""

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.kwargs: dict = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


def _sdk(response=None, error: Exception | None = None) -> SimpleNamespace:
    return SimpleNamespace(messages=_FakeMessages(response, error))


def _response(stop_reason: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=12, output_tokens=3),
    )


_VALID = '{"picks": [{"transaction_ref": "t1", "account_code": "5.1.01", "confidence": "alta", "justification": "Tarifa"}]}'


def test_refusal_yields_no_answer():
    cases = {
        "refusal": "Não posso ajudar com isso.",
        "max_tokens": '{"picks": [{"transaction_ref": "t1", "account_co',
    }
    for stop_reason, text in cases.items():
        sdk = _sdk(_response(stop_reason, text))
        result = AnthropicModelClient("chave-de-teste", "claude-haiku-5-5", sdk=sdk).suggest(system="s", user="u")
        assert result.answer is None
        assert result.stop_reason == stop_reason
        assert (result.input_tokens, result.output_tokens) == (12, 3)
    sdk = _sdk(_response("end_turn", _VALID))
    result = AnthropicModelClient("chave-de-teste", "claude-haiku-5-5", sdk=sdk).suggest(system="s", user="u")
    assert result.answer is not None and result.answer.picks[0].account_code == "5.1.01"
    kwargs = sdk.messages.kwargs
    assert kwargs["model"] == "claude-haiku-5-5"
    assert kwargs["max_tokens"] == 4096
    assert kwargs["output_config"]["effort"] == "low"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert kwargs["output_config"]["format"]["schema"]["properties"]["picks"]["type"] == "array"
    assert kwargs["messages"] == [{"role": "user", "content": "u"}]
    assert "temperature" not in kwargs and "top_p" not in kwargs and "output_format" not in kwargs


def test_invalid_output_yields_no_answer_without_content():
    for text in ('{"picks": [{"transaction_ref": "t1"', "JOAQUIM PEREIRA", '{"outra": 1}'):
        result = AnthropicModelClient("chave-de-teste", "claude-haiku-5-5", sdk=_sdk(_response("end_turn", text))).suggest(system="s", user="u")
        assert result.answer is None
        assert result.stop_reason == "invalid_output"
        assert (result.input_tokens, result.output_tokens) == (12, 3)


def test_api_error_does_not_carry_content():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(message="conteúdo secreto", request=request)
    client = AnthropicModelClient("chave-de-teste", "claude-haiku-5-5", sdk=_sdk(error=error))
    with pytest.raises(ModelCallError) as caught:
        client.suggest(system="s", user="PIX JOAQUIM")
    assert "JOAQUIM" not in str(caught.value) and "secreto" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_fake_client_answers_known_refs():
    _system, user = build_prompt([("5.1.01", "Despesas", "expense")], [("t1", "outflow", "10.00", "TARIFA"), ("t2", "outflow", "5.00", "TARIFA")])
    fake = FakeModelClient({"t1": ("5.1.01", "alta")})
    result = fake.suggest(system="s", user=user)
    assert fake.calls == 1
    assert [(pick.transaction_ref, pick.account_code) for pick in result.answer.picks] == [("t1", "5.1.01")]
    everyone = FakeModelClient({"*": ("5.1.01", "baixa")}).suggest(system="s", user=user)
    assert [pick.transaction_ref for pick in everyone.answer.picks] == ["t1", "t2"]


def test_fake_client_behaves_like_the_sdk():
    _system, user = build_prompt([("5.1.01", "Despesas", "expense")], [("t1", "outflow", "10.00", "TARIFA")])
    for stop_reason in ("refusal", "max_tokens"):
        result = FakeModelClient({"t1": ("5.1.01", "alta")}, stop_reason=stop_reason).suggest(system="s", user=user)
        assert result.answer is None and result.stop_reason == stop_reason and result.input_tokens == 100
    failing = FakeModelClient({}, fail_on_calls={2})
    failing.suggest(system="s", user=user)
    with pytest.raises(ModelCallError):
        failing.suggest(system="s", user=user)
    assert failing.calls == 2
