from __future__ import annotations

from contabil.audit.hash import content_hash
from contabil.closing.checklist import BY_ID, ItemDecision, blocking_pending, decision_error, evaluate


def _counts(**overrides: object) -> dict:
    base: dict = {
        "journals_pending_approval": 0,
        "journals_approved": 0,
        "journals_draft": 0,
        "import_batches_open": 0,
        "reconciliation_pending": 0,
        "documents": 0,
        "document_requests_open": 0,
        "trial_debit": "0",
        "trial_credit": "0",
    }
    base.update(overrides)
    return base


def _item(items: list[dict], item_id: str) -> dict:
    return next(item for item in items if item["item_id"] == item_id)


def test_pending_journals_block_and_drafts_do_not() -> None:
    items = evaluate(_counts(journals_pending_approval=2, journals_draft=1), {})
    assert _item(items, "journals_pending_approval")["status"] == "blocked"
    assert _item(items, "journals_draft")["status"] == "pending"
    assert _item(items, "journals_draft")["blocking"] is False
    pending = {item["item_id"] for item in blocking_pending(items)}
    assert "journals_pending_approval" in pending
    assert "journals_draft" not in pending
    assert "trial_balance_review" in pending


def test_not_applicable_clears_a_blocker() -> None:
    decisions = {
        "journals_pending_approval": ItemDecision("not_applicable", "Não há movimento nesta competência.", "approver"),
        "trial_balance_review": ItemDecision("completed", None, "approver"),
    }
    items = evaluate(_counts(journals_pending_approval=2), decisions)
    assert _item(items, "journals_pending_approval")["status"] == "not_applicable"
    assert blocking_pending(items) == []


def test_short_reason_is_rejected() -> None:
    assert decision_error(BY_ID["journals_pending_approval"], "not_applicable", "curto")
    assert decision_error(BY_ID["journals_approved"], "completed", None)
    assert decision_error(BY_ID["trial_balance_review"], "completed", None) is None


def test_unbalanced_trial_balance_blocks() -> None:
    items = evaluate(_counts(trial_debit="10", trial_credit="8"), {})
    assert _item(items, "trial_balance")["status"] == "blocked"


def test_open_document_requests_block_close() -> None:
    items = evaluate(_counts(document_requests_open=2), {})
    item = _item(items, "document_requests_open")
    assert item["status"] == "blocked"
    assert item["blocking"] is True
    assert item["href"] == "/app/rastro/pendencias"
    assert "document_requests_open" in {pending["item_id"] for pending in blocking_pending(items)}
    clear = evaluate(_counts(), {})
    assert _item(clear, "document_requests_open")["status"] == "completed"


def test_snapshot_hash_ignores_key_order() -> None:
    first = content_hash({"b": 1, "a": {"d": 2, "c": 3}})
    second = content_hash({"a": {"c": 3, "d": 2}, "b": 1})
    assert first == second
    assert len(first) == 64
