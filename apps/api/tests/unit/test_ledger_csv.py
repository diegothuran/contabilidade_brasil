from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from contabil.ledger.csv_export import (
    DISCLAIMER,
    account_ledger_csv,
    cnpj_br,
    money_br,
    period_label,
    safe_text,
    trial_balance_csv,
)

GENERATED = datetime(2026, 10, 1, 15, 30, tzinfo=timezone.utc)


def _rows(content: str) -> list[list[str]]:
    assert content.startswith("﻿")
    return list(csv.reader(io.StringIO(content[1:], newline=""), delimiter=";"))


def _balance() -> dict:
    return {
        "rows": [
            {
                "code": "1.1.02",
                "name": "Banco; conta movimento",
                "opening_balance": "100",
                "debit": "1234.5",
                "credit": "0",
                "balance": "1234.5",
                "closing_balance": "1334.5",
            },
            {
                "code": "2.1.01",
                "name": "Fornecedores",
                "opening_balance": "-100",
                "debit": "0",
                "credit": "1234.5",
                "balance": "-1234.5",
                "closing_balance": "-1334.5",
            },
        ],
        "debit_total": "1234.5",
        "credit_total": "1234.5",
    }


def test_money_uses_comma_and_two_places() -> None:
    assert money_br("1234.5") == "1234,50"
    assert money_br("-10") == "-10,00"
    assert money_br("0.005") == "0,01"
    assert money_br("-0.001") == "0,00"


def test_formula_like_text_is_neutralized() -> None:
    assert safe_text("=SOMA(A1)") == "'=SOMA(A1)"
    assert safe_text("-ajuste") == "'-ajuste"
    assert safe_text("Aluguel") == "Aluguel"
    assert safe_text(None) == ""


def test_labels() -> None:
    assert cnpj_br("12345678000195") == "12.345.678/0001-95"
    assert period_label(2026, 9) == "setembro de 2026"


def test_trial_balance_csv_has_header_columns_and_totals() -> None:
    content = trial_balance_csv(
        entity_name="Empresa Alfa", cnpj="12345678000195", period="setembro de 2026", generated_at=GENERATED, balance=_balance()
    )
    assert "\r\n" in content
    rows = _rows(content)
    assert rows[0] == ["Balancete"]
    assert rows[2] == ["CNPJ", "12.345.678/0001-95"]
    assert rows[4] == ["Gerado em", "01/10/2026 12:30 (Brasília)"]
    assert [DISCLAIMER] in rows
    header = rows.index(["Código", "Conta", "Saldo anterior", "Débito", "Crédito", "Saldo atual"])
    assert rows[header + 1] == ["1.1.02", "Banco; conta movimento", "100,00", "1234,50", "0,00", "1334,50"]
    assert rows[header + 3] == ["", "Totais", "0,00", "1234,50", "1234,50", "0,00"]


def test_account_ledger_runs_from_opening_balance() -> None:
    ledger = {
        "code": "1.1.02",
        "name": "Banco",
        "opening_balance": "100",
        "lines": [
            {"entry_date": "2026-09-05", "description": "=cmd", "journal_id": "jnl_1", "side": "debit", "amount": "50"},
            {"entry_date": "2026-09-20", "description": "Tarifa", "journal_id": "jnl_2", "side": "credit", "amount": "30.25"},
        ],
    }
    rows = _rows(
        account_ledger_csv(entity_name="Empresa Alfa", cnpj="12345678000195", period="setembro de 2026", generated_at=GENERATED, ledger=ledger)
    )
    assert rows[0] == ["Razão da conta 1.1.02 Banco"]
    header = rows.index(["Data", "Histórico", "Lançamento", "Débito", "Crédito", "Saldo"])
    assert rows[header + 1] == ["", "Saldo anterior", "", "", "", "100,00"]
    assert rows[header + 2] == ["05/09/2026", "'=cmd", "jnl_1", "50,00", "", "150,00"]
    assert rows[header + 3] == ["20/09/2026", "Tarifa", "jnl_2", "", "30,25", "119,75"]
    assert rows[header + 4] == ["", "Saldo atual", "", "", "", "119,75"]
