"""Frases fixas do resumo do mês para o empresário. Função pura, sem IA (ADR 034)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from contabil.platform.money import format_signed

SCHEMA_VERSION = "1.0.0"
MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)  # fmt: skip
CENT = Decimal("0.01")


def brl(value: Decimal) -> str:
    """Valor no formato brasileiro (1.234,56), só para as frases."""
    text = format(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP), ",.2f")
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def compose_summary(*, revenue: Decimal, expense: Decimal, cash: Decimal, fiscal_year: int, month: int) -> dict:
    result = revenue - expense
    margin: Decimal | None = None
    if revenue != 0:
        margin = (result / revenue * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    sentences = [
        f"Em {MONTHS[month - 1]}/{fiscal_year}, a empresa faturou R$ {brl(revenue)} e gastou R$ {brl(expense)}.",
        f"O resultado foi lucro de R$ {brl(result)}." if result >= 0 else f"O resultado foi prejuízo de R$ {brl(abs(result))}.",
    ]
    if margin is None:
        sentences.append("Não houve faturamento na competência.")
    else:
        whole = int(abs(margin).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        verb = "sobraram" if margin >= 0 else "faltaram"
        sentences.append(f"De cada R$ 100 faturados, {verb} R$ {whole}.")
    sentences.append(f"No fim do mês, havia R$ {brl(cash)} nas contas bancárias.")
    return {
        "schema_version": SCHEMA_VERSION,
        "competence": f"{fiscal_year:04d}-{month:02d}",
        "revenue": format_signed(revenue),
        "expense": format_signed(expense),
        "result": format_signed(result),
        "cash": format_signed(cash),
        "margin_percent": None if margin is None else format(margin, "f"),
        "sentences": sentences,
    }
