from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from contabil.platform.conferences import load_thresholds
from contabil.reconciliation.alerts import AlertTx, alert_dict, statement_alerts

BASE = date(2026, 10, 1)


def tx(tid, day, *, bank="b1", entity="e1", amount="100.00", direction="outflow", description="PAGTO FORNECEDOR ALFA LTDA"):
    return AlertTx(tid, bank, entity, BASE + timedelta(days=day), Decimal(amount), direction, description)


def test_duplicate_payment_within_window():
    alerts = statement_alerts([tx("t1", 0), tx("t2", 3)], load_thresholds())
    assert len(alerts) == 1
    assert alerts[0].kind == "duplicate_payment"
    assert alerts[0].transaction_ids == ("t1", "t2")
    assert "3 dia(s)" in alerts[0].explanation


def test_duplicate_payment_outside_window():
    assert statement_alerts([tx("t1", 0), tx("t2", 4)], load_thresholds()) == []


def test_duplicate_requires_same_amount_and_outflow():
    th = load_thresholds()
    assert statement_alerts([tx("t1", 0), tx("t2", 1, amount="100.01")], th) == []
    assert statement_alerts([tx("t1", 0, direction="inflow"), tx("t2", 1, direction="inflow")], th) == []


def test_duplicate_requires_similar_description():
    th = load_thresholds()
    assert statement_alerts([tx("t1", 0, description="Aluguel sala"), tx("t2", 1, description="Energia eletrica")], th) == []
    assert len(statement_alerts([tx("t1", 0, description="Pix Maria Silva"), tx("t2", 1, description="TED Maria Silva")], th)) == 1


def test_own_transfer_between_entity_accounts():
    alerts = statement_alerts(
        [tx("t1", 0, bank="b1", description="x"), tx("t2", 1, bank="b2", direction="inflow", description="y")],
        load_thresholds(),
    )
    assert [a.kind for a in alerts] == ["own_transfer"]
    assert alerts[0].transaction_ids == ("t1", "t2")


def test_own_transfer_ignores_other_entity():
    alerts = statement_alerts(
        [tx("t1", 0, bank="b1"), tx("t2", 1, bank="b2", entity="e2", direction="inflow")],
        load_thresholds(),
    )
    assert alerts == []


def test_alert_carries_rule_version():
    alert = statement_alerts([tx("t1", 0), tx("t2", 1)], load_thresholds())[0]
    assert alert.rule_version == "2026.11-provisorio"
    assert set(alert_dict(alert)) == {"kind", "transaction_ids", "explanation", "rule_version"}


def test_own_transfer_window_edges():
    th = load_thresholds()
    two_days = [tx("t1", 0, bank="b1"), tx("t2", 2, bank="b2", direction="inflow")]
    three_days = [tx("t1", 0, bank="b1"), tx("t2", 3, bank="b2", direction="inflow")]
    assert [a.kind for a in statement_alerts(two_days, th)] == ["own_transfer"]
    assert statement_alerts(three_days, th) == []


def test_duplicate_at_three_days_is_not_also_own_transfer():
    alerts = statement_alerts([tx("t1", 0), tx("t2", 3)], load_thresholds())
    assert [a.kind for a in alerts] == ["duplicate_payment"]


def test_three_equal_payments_make_three_distinct_pairs():
    alerts = statement_alerts([tx("t1", 0), tx("t2", 1), tx("t3", 2)], load_thresholds())
    assert [a.kind for a in alerts] == ["duplicate_payment"] * 3
    assert sorted(a.transaction_ids for a in alerts) == [("t1", "t2"), ("t1", "t3"), ("t2", "t3")]
