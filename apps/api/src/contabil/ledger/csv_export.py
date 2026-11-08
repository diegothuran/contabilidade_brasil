"""Balancete, razão, DRE e Balanço em CSV para o Excel brasileiro: BOM, ponto e vírgula, vírgula decimal."""

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


def _header(
    writer, title: str, entity_name: str, cnpj: str, period: str, generated_at: datetime, responsible: str | None = None
) -> None:
    writer.writerow([title])
    writer.writerow(["Empresa", safe_text(entity_name)])
    writer.writerow(["CNPJ", cnpj_br(cnpj)])
    writer.writerow(["Competência", period])
    writer.writerow(["Gerado em", generated_at.astimezone(BRASILIA).strftime("%d/%m/%Y %H:%M") + " (Brasília)"])
    if responsible:
        writer.writerow(["Responsável técnico", safe_text(responsible)])
    writer.writerow([DISCLAIMER])
    writer.writerow([])


def _responsible(report: dict) -> str | None:
    """Nome e CRC do contador da empresa, para o cabeçalho da DRE e do Balanço (ADR 030)."""
    accountant = (report.get("signatories") or {}).get("accountant")
    return f"{accountant['name']} — {accountant['caption']}" if accountant else None


def _signatures(writer, report: dict) -> None:
    """Bloco de assinaturas no fim da demonstração. Sem cadastro, a linha diz isso e o arquivo sai mesmo assim."""
    signatories = report.get("signatories") or {}
    accountant = signatories.get("accountant")
    representative = signatories.get("legal_representative")
    writer.writerow([])
    writer.writerow(["Assinaturas"])
    if accountant:
        writer.writerow(["Responsável técnico", safe_text(accountant["name"]), safe_text(accountant["caption"])])
    else:
        writer.writerow(["Responsável técnico não cadastrado"])
    if representative:
        writer.writerow(["Representante legal", safe_text(representative["name"]), safe_text(representative["caption"])])
    else:
        writer.writerow(["Representante legal não cadastrado"])


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


def income_statement_csv(*, entity_name: str, cnpj: str, period: str, generated_at: datetime, report: dict) -> str:
    def write(writer) -> None:
        _header(writer, "Demonstração do resultado (gerencial)", entity_name, cnpj, period, generated_at, _responsible(report))
        writer.writerow(["Código", "Conta", "Mês", "Acumulado no ano"])
        for section in report["sections"]:
            writer.writerow(["", section["title"].upper(), money_br(section["month"]), money_br(section["year_to_date"])])
            for group in section["groups"]:
                writer.writerow([safe_text(group["code"]), safe_text(group["name"]), money_br(group["month"]), money_br(group["year_to_date"])])
                for row in group["rows"]:
                    writer.writerow([safe_text(row["code"]), safe_text(row["name"]), money_br(row["month"]), money_br(row["year_to_date"])])
        writer.writerow(["", "Resultado do período", money_br(report["result"]["month"]), money_br(report["result"]["year_to_date"])])
        writer.writerow([])
        writer.writerow(["Receitas e despesas em valor positivo; resultado negativo é prejuízo. O encerramento do exercício não entra."])
        _signatures(writer, report)

    return _render(write)


def balance_sheet_csv(*, entity_name: str, cnpj: str, period: str, generated_at: datetime, report: dict) -> str:
    def write(writer) -> None:
        _header(writer, "Balanço patrimonial (gerencial)", entity_name, cnpj, period, generated_at, _responsible(report))
        writer.writerow(["Código", "Conta", "Saldo"])
        for section in report["sections"]:
            writer.writerow(["", section["title"].upper(), money_br(section["balance"])])
            for group in section["groups"]:
                writer.writerow([safe_text(group["code"]), safe_text(group["name"]), money_br(group["balance"])])
                for row in group["rows"]:
                    writer.writerow([safe_text(row["code"]), safe_text(row["name"]), money_br(row["balance"])])
            if "unclosed_result" in section and Decimal(section["unclosed_result"]) != 0:
                writer.writerow(["", "Resultado do exercício não encerrado", money_br(section["unclosed_result"])])
        writer.writerow([])
        writer.writerow(["", "Total do ativo", money_br(report["total_assets"])])
        writer.writerow(["", "Total do passivo e patrimônio líquido", money_br(report["total_liabilities_and_equity"])])
        writer.writerow(["", "Diferença", money_br(report["difference"])])
        writer.writerow([])
        writer.writerow(["Saldos na natureza da conta: ativo devedor; passivo e patrimônio líquido credores."])
        _signatures(writer, report)

    return _render(write)
