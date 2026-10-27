from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "examples"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_contract_fixtures_validate() -> None:
    pairs = [
        ("journal-entry.schema.json", "journal-entry.example.json"),
        ("import-batch.schema.json", "import-batch.example.json"),
        ("reconciliation-case.schema.json", "reconciliation-case.example.json"),
        ("close-run.schema.json", "close-run.example.json"),
        ("source-document.schema.json", "source-document.example.json"),
        ("document-request.schema.json", "document-request.example.json"),
        ("regulatory-obligation.schema.json", "regulatory-obligation.example.json"),
        ("audit-event.schema.json", "audit-event.example.json"),
    ]
    for schema_name, example_name in pairs:
        schema = read_json(SCHEMAS / schema_name)
        errors = list(Draft202012Validator(schema).iter_errors(read_json(EXAMPLES / example_name)))
        assert not errors, [error.message for error in errors]


def test_journal_is_balanced() -> None:
    journal = read_json(EXAMPLES / "journal-entry.example.json")
    debit = sum((Decimal(x["amount"]) for x in journal["lines"] if x["side"] == "debit"), Decimal("0"))
    credit = sum((Decimal(x["amount"]) for x in journal["lines"] if x["side"] == "credit"), Decimal("0"))
    assert debit == credit
    assert journal["status"] == "published"
    assert journal["audit_event_id"]


def test_closed_period_fixture_has_evidence() -> None:
    close_run = read_json(EXAMPLES / "close-run.example.json")
    assert close_run["status"] == "closed"
    assert close_run["snapshot_ref"]
    assert close_run["evidence_package_ref"]
    assert all(item["status"] in {"completed", "not_applicable"} for item in close_run["checklist"] if item["blocking"])


def test_accepted_obligation_has_protocol() -> None:
    obligation = read_json(EXAMPLES / "regulatory-obligation.example.json")
    assert obligation["status"] == "accepted"
    accepted = [item for item in obligation["transmissions"] if item["status"] == "accepted"]
    assert accepted and accepted[0]["protocol"] and accepted[0]["receipt_ref"]


def test_security_config_prevents_autonomous_effects() -> None:
    config = yaml.safe_load((ROOT / "configs/product.yaml").read_text(encoding="utf-8"))
    assert config["security"]["ai_can_publish_journal"] is False
    assert config["security"]["ai_can_transmit_obligation"] is False
    assert config["ledger"]["allow_direct_database_writes"] is False


def test_examples_do_not_contain_secret_markers() -> None:
    content = " ".join(path.read_text(encoding="utf-8") for path in EXAMPLES.glob("*.json")).lower()
    for marker in ("access_token", "refresh_token", "private_key", "client_secret", "password"):
        assert marker not in content
