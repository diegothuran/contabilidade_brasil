"""Balancete e razão em CSV para o Excel brasileiro: BOM, ponto e vírgula, vírgula decimal."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from contabil.platform.clock import BRASILIA

DISCLAIMER = "Relatório gerencial gerado pelo sistema. Não é livro contábil oficial."

MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def money_br(value: str | Decimal) -> str:
    """1234.5 -> 1234,50; -10 -> -10,00. Sem separador de milhar, para o Excel ler como número."""
    amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount == 0:
        amount = Decimal("0.00")
    return format(amount, "f").replace(".", ",")


def safe_text(value: str | None) -> str:
    """Texto livre (histórico, nome) não vira fórmula quando o Excel abre o arquivo."""
    text = value or ""
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def date_br(value: date | str) -> str:
    parsed = date.fromisoformat(value) if isinstance(value, str) else value
    return parsed.strftime("%d/%m/%Y")


def cnpj_br(digits: str) -> str:
    if len(digits) != 14 or not digits.isdigit():
        return digits
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def period_label(fiscal_year: int, month: int) -> str:
    return f"{MONTHS[month - 1]} de {fiscal_year}"


def _header(writer, title: str, entity_name: str, cnpj: str, period: str, generated_at: datetime) -> None:
    writer.writerow([title])
    writer.writerow(["Empresa", safe_text(entity_name)])
    writer.writerow(["CNPJ", cnpj_br(cnpj)])
    writer.writerow(["Competência", period])
    writer.writerow(["Gerado em", generated_at.astimezone(BRASILIA).strftime("%d/%m/%Y %H:%M") + " (Brasília)"])
    writer.writerow([DISCLAIMER])
    writer.writerow([])


def _render(rows_writer) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    rows_writer(writer)
    return "﻿" + buffer.getvalue()


def trial_balance_csv(*, entity_name: str, cnpj: str, period: str, generated_at: datetime, balance: dict) -> str:
    def write(writer) -> None:
        _header(writer, "Balancete", entity_name, cnpj, period, generated_at)
        writer.writerow(["Código", "Conta", "Saldo anterior", "Débito", "Crédito", "Saldo atual"])
        opening_total = Decimal("0")
        closing_total = Decimal("0")
        for row in balance["rows"]:
            opening_total += Decimal(row["opening_balance"])
            closing_total += Decimal(row["closing_balance"])
            writer.writerow(
                [
                    safe_text(row["code"]),
                    safe_text(row["name"]),
                    money_br(row["opening_balance"]),
                    money_br(row["debit"]),
                    money_br(row["credit"]),
                    money_br(row["closing_balance"]),
                ]
            )
        writer.writerow(
            [
                "",
                "Totais",
                money_br(opening_total),
                money_br(balance["debit_total"]),
                money_br(balance["credit_total"]),
                money_br(closing_total),
            ]
        )
        writer.writerow([])
        writer.writerow(["Saldos positivos são devedores; negativos são credores."])

    return _render(write)


def account_ledger_csv(*, entity_name: str, cnpj: str, period: str, generated_at: datetime, ledger: dict) -> str:
    def write(writer) -> None:
        _header(writer, safe_text(f"Razão da conta {ledger['code']} {ledger['name']}"), entity_name, cnpj, period, generated_at)
        writer.writerow(["Data", "Histórico", "Lançamento", "Débito", "Crédito", "Saldo"])
        running = Decimal(ledger["opening_balance"])
        writer.writerow(["", "Saldo anterior", "", "", "", money_br(running)])
        for line in ledger["lines"]:
            amount = Decimal(line["amount"])
            is_debit = line["side"] == "debit"
            running += amount if is_debit else -amount
            writer.writerow(
                [
                    date_br(line["entry_date"]),
                    safe_text(line["description"]),
                    line["journal_id"],
                    money_br(amount) if is_debit else "",
                    "" if is_debit else money_br(amount),
                    money_br(running),
                ]
            )
        writer.writerow(["", "Saldo atual", "", "", "", money_br(running)])
        writer.writerow([])
        writer.writerow(["Saldos positivos são devedores; negativos são credores."])

    return _render(write)
