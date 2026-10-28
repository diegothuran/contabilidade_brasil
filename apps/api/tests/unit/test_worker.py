from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from contabil.worker import _complete_operation, _fail_operation

_EARLIER = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _session(operation: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(scalar=lambda _: operation)


def _operation(status: str) -> SimpleNamespace:
    return SimpleNamespace(status=status, error_code=None, updated_at=_EARLIER)


def test_completed_operation_records_when_it_finished() -> None:
    operation = _operation("running")
    _complete_operation(_session(operation), "tenant", "op_1")
    assert operation.status == "completed"
    assert operation.updated_at > _EARLIER


def test_failed_operation_records_when_it_failed() -> None:
    operation = _operation("accepted")
    _fail_operation(_session(operation), "tenant", "op_1")
    assert operation.status == "failed"
    assert operation.error_code == "handler_failed"
    assert operation.updated_at > _EARLIER


def test_completed_operation_does_not_become_failed() -> None:
    operation = _operation("completed")
    _fail_operation(_session(operation), "tenant", "op_1")
    assert operation.status == "completed"
    assert operation.updated_at == _EARLIER
