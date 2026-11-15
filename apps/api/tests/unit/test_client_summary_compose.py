from decimal import Decimal

from contabil.client_summaries.compose import compose_summary


def test_compose_profit_sentences():
    payload = compose_summary(
        revenue=Decimal("1000"), expense=Decimal("710"), cash=Decimal("500"), fiscal_year=2026, month=9
    )
    assert payload["schema_version"] == "1.0.0"
    assert payload["competence"] == "2026-09"
    assert payload["revenue"] == "1000"
    assert payload["expense"] == "710"
    assert payload["result"] == "290"
    assert payload["cash"] == "500"
    assert payload["margin_percent"] == "29.0"
    assert payload["sentences"] == [
        "Em setembro/2026, a empresa faturou R$ 1.000,00 e gastou R$ 710,00.",
        "O resultado foi lucro de R$ 290,00.",
        "De cada R$ 100 faturados, sobraram R$ 29.",
        "No fim do mês, havia R$ 500,00 nas contas bancárias.",
    ]


def test_compose_loss_sentences():
    payload = compose_summary(
        revenue=Decimal("1000"), expense=Decimal("1250.50"), cash=Decimal("1234.56"), fiscal_year=2026, month=8
    )
    assert payload["result"] == "-250.5"
    assert payload["margin_percent"] == "-25.1"
    assert payload["sentences"] == [
        "Em agosto/2026, a empresa faturou R$ 1.000,00 e gastou R$ 1.250,50.",
        "O resultado foi prejuízo de R$ 250,50.",
        "De cada R$ 100 faturados, faltaram R$ 25.",
        "No fim do mês, havia R$ 1.234,56 nas contas bancárias.",
    ]


def test_compose_without_revenue():
    payload = compose_summary(revenue=Decimal("0"), expense=Decimal("40"), cash=Decimal("0"), fiscal_year=2026, month=1)
    assert payload["margin_percent"] is None
    assert payload["sentences"][1] == "O resultado foi prejuízo de R$ 40,00."
    assert payload["sentences"][2] == "Não houve faturamento na competência."


def test_compose_rounds_sentence_margin_once():
    payload = compose_summary(
        revenue=Decimal("10000"), expense=Decimal("7055"), cash=Decimal("0"), fiscal_year=2026, month=9
    )
    assert payload["margin_percent"] == "29.5"
    assert payload["sentences"][2] == "De cada R$ 100 faturados, sobraram R$ 29."
