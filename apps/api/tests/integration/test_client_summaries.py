from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from contabil.platform.db import get_admin_engine


def _insert_summary(connection, status: str = "published") -> None:
    connection.execute(
        text(
            "INSERT INTO client_summaries (id, tenant_id, legal_entity_id, period_id, status, payload, created_by, created_at) "
            "VALUES ('cs_x', 'tenant_demo', 'le_test', 'le_test-2026-09', :status, CAST(:payload AS jsonb), 'preparer', now())"
        ),
        {"status": status, "payload": json.dumps({"revenue": "1"})},
    )


def test_published_payload_is_immutable(client, tokens, world):
    del client, tokens, world
    with get_admin_engine().begin() as connection:
        _insert_summary(connection)
    with pytest.raises(DBAPIError):
        with get_admin_engine().begin() as connection:
            connection.execute(text("UPDATE client_summaries SET payload = CAST('{}' AS jsonb) WHERE id = 'cs_x'"))
    with pytest.raises(DBAPIError):
        with get_admin_engine().begin() as connection:
            connection.execute(text("DELETE FROM client_summaries WHERE id = 'cs_x'"))
