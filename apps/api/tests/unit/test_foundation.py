from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from contabil.audit.hash import canonical_payload, chain_hash
from contabil.ledger.schemas import JournalCreate
from contabil.platform.money import format_amount, format_signed, parse_amount
from contabil.seed.cnpj import cnpj_digits


def test_money_rejects_float_text_and_keeps_scale() -> None:
    assert parse_amount("10.50") == Decimal("10.50")
    assert format_amount(Decimal("10.500000")) == "10.5"
    assert format_signed(Decimal("-2.5")) == "-2.5"
    with pytest.raises(Exception):
        parse_amount("10.1234567")
    with pytest.raises(Exception):
        parse_amount("-1")


def test_journal_schema_rejects_numeric_amount() -> None:
    with pytest.raises(ValidationError):
        JournalCreate.model_validate(
            {
                "legal_entity_id": "le",
                "period_id": "p",
                "currency": "BRL",
                "entry_date": "2026-09-15",
                "description": "Teste",
                "lines": [
                    {"account_id": "a", "side": "debit", "amount": 10, "description": "D"},
                    {"account_id": "b", "side": "credit", "amount": "10", "description": "C"},
                ],
            }
        )


def test_audit_hash_changes_when_payload_changes() -> None:
    base = dict(
        schema_version="1.0.0",
        event_id="aud_1",
        tenant_id="tenant_demo",
        event_type="journal_published",
        actor_kind="user",
        actor_ref="approver",
        occurred_at="2026-09-15T12:00:00Z",
        target_type="journal",
        target_ref="jnl_1",
        reason=None,
        metadata={"action": "journal_published"},
    )
    first = chain_hash(None, canonical_payload(**base))
    second = chain_hash(first, canonical_payload(**{**base, "event_id": "aud_2"}))
    assert first != second
    assert len(first) == 64


def test_cnpj_check_digits() -> None:
    number = cnpj_digits("042520110001")
    assert number == "04252011000110"
    assert cnpj_digits(number[:12]) == number
