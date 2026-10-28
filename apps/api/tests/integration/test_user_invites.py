from __future__ import annotations

from sqlalchemy import select

from contabil.identity.directory import get_user_directory
from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.platform.errors import DomainError
from contabil.tables import AuditEvent, Membership
from tests.integration.test_phase_a import _post


class _OfficeDirectory:
    def __init__(self) -> None:
        self.users: dict[str, str] = {}

    def create_user(self, username: str, email: str, display_name: str, tenant_id: str) -> None:
        del email, display_name
        current = self.users.get(username)
        if current is None:
            self.users[username] = tenant_id
            return
        if current != tenant_id:
            raise DomainError(409, "Usuário de outro escritório", "Este nome de usuário já pertence a outro escritório.")


def test_admin_invites_and_lists_without_email(client, tokens, world, app):
    del world
    directory = _OfficeDirectory()
    app.dependency_overrides[get_user_directory] = lambda: directory
    try:
        created = _post(
            client,
            tokens["admin"],
            "/v1/users",
            {"username": "Ana", "display_name": "Ana Costa", "email": "ana@example.com", "roles": ["preparer", "viewer"]},
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["user_id"] == "ana"
        assert directory.users == {"ana": "tenant_demo"}
        assert "email" not in body
        listed = client.get("/v1/users", headers={"Authorization": f"Bearer {tokens['admin']}"})
        assert listed.status_code == 200
        match = [item for item in listed.json()["items"] if item["user_id"] == "ana"]
        assert match == [{"user_id": "ana", "display_name": "Ana Costa", "roles": ["preparer", "viewer"]}]
        assert "ana@example.com" not in listed.text
        session = session_factory(admin=True)()
        try:
            apply_tenant(session, "tenant_demo")
            event = session.scalar(
                select(AuditEvent).where(AuditEvent.tenant_id == "tenant_demo", AuditEvent.target_ref == "ana")
            )
            assert event is not None
            assert event.details["action"] == "user_invited"
            assert "email" not in event.details
            membership = session.scalar(select(Membership).where(Membership.user_id == "ana"))
            assert membership is not None
        finally:
            session.close()
    finally:
        app.dependency_overrides.pop(get_user_directory, None)


def test_only_admin_invites(client, tokens, world, app):
    del world
    app.dependency_overrides[get_user_directory] = lambda: _OfficeDirectory()
    try:
        body = {"username": "bia", "display_name": "Bia", "email": "bia@example.com", "roles": ["viewer"]}
        assert _post(client, tokens["viewer"], "/v1/users", body).status_code == 403
        assert _post(client, tokens["preparer"], "/v1/users", body).status_code == 403
        assert client.get("/v1/users", headers={"Authorization": f"Bearer {tokens['viewer']}"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_user_directory, None)


def test_repeated_username_is_conflict(client, tokens, world, app):
    del world
    app.dependency_overrides[get_user_directory] = lambda: _OfficeDirectory()
    try:
        body = {"username": "caio", "display_name": "Caio", "email": "caio@example.com", "roles": ["viewer"]}
        assert _post(client, tokens["admin"], "/v1/users", body).status_code == 201
        duplicate = _post(client, tokens["admin"], "/v1/users", body)
        assert duplicate.status_code == 409
        assert duplicate.json()["title"] == "Usuário já faz parte do escritório"
    finally:
        app.dependency_overrides.pop(get_user_directory, None)
