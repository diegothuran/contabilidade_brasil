from __future__ import annotations

from datetime import date

from sqlalchemy import select

from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.tables import DocumentRequest


class _FakeDirectory:
    def __init__(self) -> None:
        self.created: dict[str, tuple[str, str, str]] = {}

    def create_test_login(self, username: str, email: str, tenant_id: str, temporary_password: str) -> bool:
        if username in self.created:
            return False
        self.created[username] = (email, tenant_id, temporary_password)
        return True


def test_round_creates_client_logins_and_current_requests_once(monkeypatch, world):
    del world
    monkeypatch.delenv("OBJECT_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_ACCESS_KEY", raising=False)
    from contabil.pilot_round import prepare_round
    from contabil.pilot_samples import load_samples

    load_samples("tenant_demo")
    today = date.today()
    directory = _FakeDirectory()
    first = prepare_round("tenant_demo", directory, today)  # type: ignore[arg-type]
    assert len(first.logins) == 5
    assert all(login.password for login in first.logins)
    assert {login.user_id for login in first.logins} == set(directory.created)
    assert all(email.endswith("@example.com") and tenant == "tenant_demo" for email, tenant, _ in directory.created.values())
    assert sum(login.requests_opened for login in first.logins) == 10, first.notes

    second = prepare_round("tenant_demo", directory, today)  # type: ignore[arg-type]
    assert all(login.password is None for login in second.logins)
    assert sum(login.requests_opened for login in second.logins) == 0

    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        rows = session.scalars(
            select(DocumentRequest).where(DocumentRequest.tenant_id == "tenant_demo", DocumentRequest.title.like("Rodada:%"))
        ).all()
        assert len(rows) == 10
        assert all(row.status == "open" and row.period_id.endswith(f"-{today.year}-{today.month:02d}") for row in rows)
        assert all(row.due_on > today for row in rows)
    finally:
        session.close()
