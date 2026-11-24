from __future__ import annotations

from contabil.suggestions.history import normalize_description, rank_history
from contabil.suggestions.types import suggestion_dict

ACCOUNTS = {
    "acc_fee": ("5.1.02", "Tarifas bancárias"),
    "acc_rent": ("5.1.03", "Aluguel"),
    "acc_energy": ("5.1.04", "Energia elétrica"),
    "acc_supplier": ("2.1.01", "Fornecedores"),
    "acc_misc": ("5.1.09", "Outras despesas"),
}


def _past(description: str, account_id: str, times: int) -> list[tuple[str, str]]:
    return [(normalize_description(description), account_id)] * times


def test_three_equal_uses_is_high():
    past = _past("Tarifa pacote de serviços", "acc_fee", 3)
    result = rank_history("TARIFA PACOTE DE SERVIÇOS", past, ACCOUNTS)
    assert len(result) == 1
    first = result[0]
    assert first.account_id == "acc_fee"
    assert first.code == "5.1.02"
    assert first.name == "Tarifas bancárias"
    assert first.confidence == "alta"
    assert first.source == "history"
    assert first.provider_version == "history-1"
    assert first.justification == "Usada 3 vez(es) para 'TARIFA PACOTE DE SERVICOS'"
    assert suggestion_dict(first)["confidence"] == "alta"


def test_one_use_is_medium():
    past = _past("Aluguel sala 3", "acc_rent", 1)
    result = rank_history("ALUGUEL SALA 3", past, ACCOUNTS)
    assert [(item.account_id, item.confidence) for item in result] == [("acc_rent", "média")]
    assert result[0].justification.startswith("Usada 1 vez(es)")


def test_partial_tokens_is_low():
    past = _past("Conta energia elétrica agosto", "acc_energy", 2) + _past("Energia solar", "acc_misc", 4)
    result = rank_history("CONTA ENERGIA ELETRICA SETEMBRO", past, ACCOUNTS)
    assert [(item.account_id, item.confidence) for item in result] == [("acc_energy", "baixa")]


def test_at_most_three_suggestions():
    past = (
        _past("Pagamento fornecedor alfa", "acc_supplier", 1)
        + _past("Pagamento fornecedor alfa", "acc_misc", 4)
        + _past("Pagamento fornecedor alfa", "acc_fee", 2)
        + _past("Pagamento fornecedor beta", "acc_rent", 5)
        + _past("Pagamento fornecedor alfa", "acc_energy", 3)
        + _past("Pagamento fornecedor alfa", "acc_unknown", 9)
    )
    result = rank_history("PAGAMENTO FORNECEDOR ALFA", past, ACCOUNTS)
    assert [(item.account_id, item.confidence) for item in result] == [
        ("acc_misc", "alta"),
        ("acc_energy", "alta"),
        ("acc_fee", "média"),
    ]


def test_justification_is_cut_at_300():
    long_description = "ALUGUEL " + " ".join(f"SALA{index}" for index in range(120))
    result = rank_history(long_description, _past(long_description, "acc_rent", 1), ACCOUNTS)
    assert len(result[0].justification) == 300
