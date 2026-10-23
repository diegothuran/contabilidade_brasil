from __future__ import annotations

from sqlalchemy import func, select, text

from contabil.bootstrap import bootstrap
from contabil.platform.db import session_factory
from contabil.tables import Membership, Tenant
from contabil.worker import verify_tenants

FORCED = (
    "memberships",
    "legal_entities",
    "establishments",
    "charts_of_accounts",
    "accounts",
    "cost_centers",
    "accounting_periods",
    "reopen_requests",
    "journal_entries",
    "journal_lines",
    "audit_events",
    "idempotency_keys",
    "source_documents",
    "import_batches",
    "import_batch_files",
    "import_rows",
    "external_refs",
    "import_batch_journals",
    "import_reports",
    "operations",
    "bank_accounts",
    "bank_statements",
    "bank_transactions",
    "reconciliation_cases",
    "reconciliation_matches",
)


def test_force_rls_covers_tenant_tables_and_spares_the_outbox(app) -> None:
    del app
    session = session_factory(admin=True)()
    try:
        rows = session.execute(
            text(
                """
                SELECT c.relname, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                """
            )
        ).all()
    finally:
        session.close()
    forced = {name: bool(flag) for name, flag in rows}
    assert set(FORCED) <= set(forced)
    assert all(forced[name] for name in FORCED)
    assert forced["outbox_events"] is False


def test_verify_tenants_reads_the_tenant_table(world, monkeypatch) -> None:
    del world
    seen: list[str] = []

    def _record(_session, tenant_id: str) -> dict:
        seen.append(tenant_id)
        return {"valid": True}

    monkeypatch.setattr("contabil.worker.verify_chain", _record)
    session = session_factory(admin=True)()
    try:
        verify_tenants(session)
    finally:
        session.close()
    assert {"tenant_demo", "tenant_other"} <= set(seen)


def test_bootstrap_is_idempotent(world) -> None:
    del world
    bootstrap("tenant_boot", "Boot", "user_boot", "Usuário Boot", ["admin", "preparer"])
    bootstrap("tenant_boot", "Outro nome", "user_boot", "Usuário Boot", ["viewer"])
    session = session_factory(admin=True)()
    try:
        count = session.scalar(select(func.count()).select_from(Membership).where(Membership.user_id == "user_boot"))
        tenant = session.get(Tenant, "tenant_boot")
    finally:
        session.close()
    assert count == 1
    assert tenant is not None
    assert tenant.name == "Boot"
