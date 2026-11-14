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


class _FakeSession:
    def __init__(self, log: list[str], name: str) -> None:
        self.log = log
        self.name = name

    def commit(self) -> None:
        self.log.append(f"commit:{self.name}")

    def rollback(self) -> None:
        self.log.append(f"rollback:{self.name}")

    def close(self) -> None:
        self.log.append(f"close:{self.name}")


def _factory(log: list[str]):
    names = iter(["relay", "remind", "verify"])

    def make() -> _FakeSession:
        return _FakeSession(log, next(names))

    return make


def test_failed_reminders_and_chain_check_keep_the_outbox_batch(monkeypatch) -> None:
    import contabil.worker as worker

    log: list[str] = []

    def boom(*_args) -> None:
        raise RuntimeError("falha fora do outbox")

    monkeypatch.setattr(worker, "relay_once", lambda session: 3)
    monkeypatch.setattr(worker, "sweep_reminders", boom)
    monkeypatch.setattr(worker, "verify_tenants", boom)
    state = worker.CycleState()
    count = worker.run_cycle(state, now=10_000.0, factory=_factory(log))
    assert count == 3
    assert log.index("commit:relay") < log.index("rollback:remind")
    assert "rollback:relay" not in log
    assert "rollback:verify" in log
    assert {"close:relay", "close:remind", "close:verify"} <= set(log)
    assert state.last_remind == 10_000.0
    assert state.last_verify == 10_000.0


def test_failed_outbox_batch_still_runs_the_other_tasks(monkeypatch) -> None:
    import contabil.worker as worker

    log: list[str] = []
    ran: list[str] = []

    def boom(_session) -> int:
        raise RuntimeError("falha no outbox")

    monkeypatch.setattr(worker, "relay_once", boom)
    monkeypatch.setattr(worker, "sweep_reminders", lambda session, today: ran.append("remind"))
    monkeypatch.setattr(worker, "verify_tenants", lambda session: ran.append("verify"))
    count = worker.run_cycle(worker.CycleState(), now=10_000.0, factory=_factory(log))
    assert count == 0
    assert "rollback:relay" in log
    assert ran == ["remind", "verify"]
    assert "commit:remind" in log and "commit:verify" in log
