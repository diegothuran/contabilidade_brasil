from __future__ import annotations

from datetime import date
from decimal import Decimal

from contabil.closing.checks import CheckRow, evaluate_checks
from contabil.platform.conferences import Thresholds

T = Thresholds(
    version="2026.11-provisorio",
    duplicate_payment_window_days=3,
    own_transfer_window_days=2,
    idle_balance_months=3,
)
START, END = date(2026, 11, 1), date(2026, 11, 30)


def _row(account_type: str, balance: str, last: date | None = date(2026, 11, 10), code: str = "1.1.01") -> CheckRow:
    return CheckRow("a1", code, "Conta", account_type, Decimal(balance), last)


def test_asset_with_credit_balance_is_inverted():
    [check] = evaluate_checks([_row("asset", "-10.00")], START, END, T)
    assert check.kind == "inverted_balance"
    assert check.amount == Decimal("-10.00")
    assert check.rule_version == "2026.11-provisorio"
    assert "Saldo credor numa conta de natureza devedora" in check.explanation


def test_revenue_with_debit_balance_is_inverted():
    [check] = evaluate_checks([_row("revenue", "5.00")], START, END, T)
    assert check.kind == "inverted_balance"
    assert "Saldo devedor numa conta de natureza credora" in check.explanation


def test_normal_balances_have_no_check():
    rows = [
        _row("asset", "10"),
        _row("expense", "1"),
        _row("liability", "-3"),
        _row("equity", "-3"),
        _row("revenue", "-3"),
    ]
    assert evaluate_checks(rows, START, END, T) == []


def test_idle_balance_uses_month_window():
    old = _row("asset", "10", date(2026, 8, 31))
    recent = _row("asset", "10", date(2026, 9, 1))
    assert [c.kind for c in evaluate_checks([old], START, END, T)] == ["idle_balance"]
    assert evaluate_checks([recent], START, END, T) == []
    assert "3 meses" in evaluate_checks([old], START, END, T)[0].explanation


def test_zero_balance_never_idle():
    assert evaluate_checks([_row("asset", "0", date(2025, 1, 1))], START, END, T) == []


def test_no_movement_at_all_is_idle_and_order_is_kind_then_code():
    rows = [_row("asset", "-1", None, code="2"), _row("asset", "1", None, code="1")]
    result = evaluate_checks(rows, START, END, T)
    assert [(c.kind, c.code) for c in result] == [("idle_balance", "1"), ("idle_balance", "2"), ("inverted_balance", "2")]
