from __future__ import annotations

import json
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import text

from contabil.platform.db import get_admin_engine, session_factory
from contabil.platform.settings import get_settings
from contabil.platform.storage import document_key, get_object_store
from contabil.worker import relay_once

from tests.integration.test_phase_a import _auth, _schemas


def _upload(client, token: str, content: bytes, **fields: str):
    data = {"document_type": "other", "legal_entity_id": "le_test", "competence": "2026-09"}
    data.update(fields)
    return client.post(
        "/v1/documents",
        files={"file": ("lote.csv", content, "text/csv")},
        data=data,
        headers=_auth(token, uuid4().hex),
    )


def _batch(client, token: str, document_id: str, kind: str, *, period: str | None, source: str):
    body = {
        "legal_entity_id": "le_test",
        "source_system": source,
        "mode": "dry_run",
        "files": [{"document_id": document_id, "kind": kind}],
    }
    if period:
        body["period_id"] = period
    return client.post("/v1/import-batches", json=body, headers=_auth(token, uuid4().hex))


def _relay() -> int:
    session = session_factory(admin=True)()
    try:
        count = relay_once(session)
        session.commit()
        return count
    finally:
        session.close()


def _validate(name: str, payload: dict) -> None:
    schema = json.loads((_schemas() / name).read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def _import_count() -> int:
    with get_admin_engine().connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM journal_entries WHERE source_type = 'import'")).scalar_one())


JOURNAL = (
    "external_journal_id;entry_date;description;account_code;side;amount;line_description;cost_center_code\n"
    "j1;2026-09-15;Compra;5.1.01;debit;10.00;Despesa;\n"
    "j1;2026-09-15;Compra;2.1.01;credit;10.00;Fornecedor;\n"
    "j2;2026-09-15;Ruim;9.9.99;debit;5.00;Sem conta;\n"
    "j2;2026-09-15;Ruim;2.1.01;credit;4.00;Valor diferente;\n"
).encode()


def test_same_hash_returns_existing_document_and_original_is_immutable(client, tokens, world):
    del world
    first = _upload(client, tokens["preparer"], b"conteudo-original")
    assert first.status_code == 201, first.text
    again = _upload(client, tokens["preparer"], b"conteudo-original")
    assert again.status_code == 200
    assert again.json()["document_id"] == first.json()["document_id"]
    _validate("source-document.schema.json", first.json())
    document_id = first.json()["document_id"]
    downloaded = client.get(f"/v1/documents/{document_id}/content", headers=_auth(tokens["viewer"]))
    assert downloaded.status_code == 200
    assert downloaded.content == b"conteudo-original"
    hidden = client.get(f"/v1/documents/{document_id}/content", headers=_auth(tokens["outsider"]))
    assert hidden.status_code == 404
    assert client.get(f"/v1/documents/{document_id}", headers=_auth(tokens["outsider"])).status_code == 404
    with pytest.raises(Exception, match="immutable"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("UPDATE source_documents SET file_name = 'trocado.csv' WHERE id = :id"), {"id": document_id})
    with pytest.raises(Exception, match="immutable"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("DELETE FROM source_documents WHERE id = :id"), {"id": document_id})
    with get_admin_engine().begin() as connection:
        connection.execute(text("UPDATE source_documents SET classification = 'interno' WHERE id = :id"), {"id": document_id})
    current = client.get(f"/v1/documents/{document_id}", headers=_auth(tokens["viewer"]))
    assert current.json()["classification"] == "interno"
    assert current.json()["original"]["file_name"] == "lote.csv"


def test_upload_rejects_oversized_file(client, tokens, world):
    del world
    settings = get_settings()
    original = settings.max_upload_bytes
    settings.max_upload_bytes = 8
    try:
        response = _upload(client, tokens["preparer"], b"123456789")
    finally:
        settings.max_upload_bytes = original
    assert response.status_code == 413


def test_dry_run_keeps_errors_and_publish_is_segregated(client, tokens, world):
    del world
    uploaded = _upload(client, tokens["preparer"], JOURNAL)
    assert uploaded.status_code == 201, uploaded.text
    created = _batch(client, tokens["preparer"], uploaded.json()["document_id"], "journal", period="le_test-2026-09", source="legado-teste")
    assert created.status_code == 202, created.text
    detail = client.get("/v1/import-batches", params={"legal_entity_id": "le_test"}, headers=_auth(tokens["preparer"]))
    batch_id = detail.json()["items"][0]["batch_id"]
    refused = client.post(f"/v1/import-batches/{batch_id}/publish", json={}, headers=_auth(tokens["approver"], uuid4().hex))
    assert refused.status_code == 409
    _relay()
    ready = client.get(f"/v1/import-batches/{batch_id}", headers=_auth(tokens["viewer"]))
    assert ready.status_code == 200, ready.text
    body = ready.json()
    assert body["status"] == "ready"
    assert body["summary"]["rows_invalid"] == 2
    assert {item["code"] for item in body["errors"]} >= {"ACCOUNT_NOT_FOUND", "JOURNAL_UNBALANCED"}
    _validate("import-batch.schema.json", body)
    assert _import_count() == 0
    own = client.post(f"/v1/import-batches/{batch_id}/publish", json={}, headers=_auth(tokens["preparer"], uuid4().hex))
    assert own.status_code == 403
    published = client.post(f"/v1/import-batches/{batch_id}/publish", json={}, headers=_auth(tokens["approver"], uuid4().hex))
    assert published.status_code == 202, published.text
    _relay()
    done = client.get(f"/v1/import-batches/{batch_id}", headers=_auth(tokens["approver"]))
    assert done.json()["status"] == "partially_published"
    assert done.json()["published_by"] == "approver"
    assert _import_count() == 1
    report = client.get(f"/v1/import-batches/{batch_id}/report", headers=_auth(tokens["viewer"]))
    assert report.status_code == 200, report.text
    explanations = " ".join(row["explanation"] for row in report.json()["rows"])
    assert "linha inválida" in explanations
    assert "conta não mapeada" in explanations


def test_repeat_import_does_not_duplicate_journals(client, tokens, world):
    del world
    content = (
        "external_journal_id;entry_date;description;account_code;side;amount;line_description;cost_center_code\n"
        "ext-1;2026-09-15;Compra;5.1.01;debit;8.00;Despesa;\n"
        "ext-1;2026-09-15;Compra;2.1.01;credit;8.00;Fornecedor;\n"
    ).encode()
    first_doc = _upload(client, tokens["preparer"], content)
    first = _batch(client, tokens["preparer"], first_doc.json()["document_id"], "journal", period="le_test-2026-09", source="legado-unico")
    assert first.status_code == 202, first.text
    _relay()
    batch_id = client.get("/v1/import-batches", params={"legal_entity_id": "le_test"}, headers=_auth(tokens["preparer"])).json()["items"][0]["batch_id"]
    assert client.post(f"/v1/import-batches/{batch_id}/publish", json={}, headers=_auth(tokens["approver"], uuid4().hex)).status_code == 202
    _relay()
    assert _import_count() == 1
    second_doc = _upload(client, tokens["preparer"], content)
    assert second_doc.status_code == 200
    second = _batch(client, tokens["preparer"], second_doc.json()["document_id"], "journal", period="le_test-2026-09", source="legado-unico")
    assert second.status_code == 202, second.text
    _relay()
    batches = client.get("/v1/import-batches", params={"legal_entity_id": "le_test"}, headers=_auth(tokens["preparer"])).json()["items"]
    repeat = next(item for item in batches if item["status"] == "ready")
    rows = client.get(f"/v1/import-batches/{repeat['batch_id']}/rows", params={"status": "already_imported"}, headers=_auth(tokens["viewer"]))
    assert rows.json()["items"]
    assert all(item["status"] == "already_imported" for item in rows.json()["items"])
    assert client.post(f"/v1/import-batches/{repeat['batch_id']}/publish", json={}, headers=_auth(tokens["approver"], uuid4().hex)).status_code == 202
    _relay()
    assert _import_count() == 1


def test_unbalanced_opening_fails_without_journals(client, tokens, world):
    del world
    content = (
        "external_account_id;account_code;debit;credit\n"
        "a1;5.1.01;10.00;0\n"
        "a2;2.1.01;0;9.00\n"
    ).encode()
    uploaded = _upload(client, tokens["preparer"], content)
    created = _batch(client, tokens["preparer"], uploaded.json()["document_id"], "opening_balance", period="le_test-2026-09", source="abertura")
    assert created.status_code == 202, created.text
    _relay()
    detail = client.get("/v1/import-batches", params={"legal_entity_id": "le_test"}, headers=_auth(tokens["preparer"])).json()["items"][0]
    assert detail["status"] == "failed"
    assert any(item["code"] == "BATCH_UNBALANCED" for item in detail["errors"])
    assert _import_count() == 0


def test_direct_publish_mode_is_rejected(client, tokens, world):
    del world
    uploaded = _upload(client, tokens["preparer"], b"external_id;code;name;account_type;postable;parent_code\n")
    response = client.post(
        "/v1/import-batches",
        json={
            "legal_entity_id": "le_test",
            "source_system": "legado",
            "mode": "publish",
            "files": [{"document_id": uploaded.json()["document_id"], "kind": "chart_of_accounts"}],
        },
        headers=_auth(tokens["preparer"], uuid4().hex),
    )
    assert response.status_code == 409
    rollback = client.post(
        "/v1/import-batches",
        json={
            "legal_entity_id": "le_test",
            "source_system": "legado",
            "mode": "rollback",
            "files": [{"document_id": uploaded.json()["document_id"], "kind": "chart_of_accounts"}],
        },
        headers=_auth(tokens["preparer"], uuid4().hex),
    )
    assert rollback.status_code == 409


def test_missing_object_becomes_dead_letter(client, tokens, world):
    del world
    uploaded = _upload(client, tokens["preparer"], b"arquivo-sumido")
    document = uploaded.json()
    created = _batch(client, tokens["preparer"], document["document_id"], "chart_of_accounts", period=None, source="sumido")
    assert created.status_code == 202, created.text
    operation_id = created.json()["operation_id"]
    store = get_object_store()
    store._s3.delete_object(Bucket=store.bucket, Key=document_key("tenant_demo", document["original"]["sha256"]))
    for _ in range(3):
        _relay()
    with get_admin_engine().connect() as connection:
        dead = connection.execute(
            text("SELECT dead_at IS NOT NULL FROM outbox_events WHERE event_type = 'ImportBatchReceived'")
        ).scalar_one()
    assert dead is True
    operation = client.get(f"/v1/operations/{operation_id}", headers=_auth(tokens["preparer"]))
    assert operation.status_code == 200
    assert operation.json()["status"] == "failed"
    assert operation.json()["error_code"] == "handler_failed"
