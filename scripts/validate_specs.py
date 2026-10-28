#!/usr/bin/env python3
"""Validate contracts, fixtures and accounting invariants."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "examples"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_pair(schemas: dict[str, dict], schema_name: str, example_name: str) -> None:
    schema = schemas[schema_name]
    errors = sorted(Draft202012Validator(schema).iter_errors(load_json(EXAMPLES / example_name)), key=lambda e: list(e.path))
    if errors:
        raise SystemExit("\n".join(f"{example_name}: {error.message}" for error in errors))


def main() -> None:
    schemas: dict[str, dict] = {}
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        schema = load_json(path)
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema

    pairs = [
        ("journal-entry.schema.json", "journal-entry.example.json"),
        ("import-batch.schema.json", "import-batch.example.json"),
        ("reconciliation-case.schema.json", "reconciliation-case.example.json"),
        ("close-run.schema.json", "close-run.example.json"),
        ("source-document.schema.json", "source-document.example.json"),
        ("document-request.schema.json", "document-request.example.json"),
        ("export-package.schema.json", "export-package.example.json"),
        ("regulatory-obligation.schema.json", "regulatory-obligation.example.json"),
        ("audit-event.schema.json", "audit-event.example.json"),
    ]
    for pair in pairs:
        validate_pair(schemas, *pair)

    journal = load_json(EXAMPLES / "journal-entry.example.json")
    debits = sum((Decimal(line["amount"]) for line in journal["lines"] if line["side"] == "debit"), Decimal("0"))
    credits = sum((Decimal(line["amount"]) for line in journal["lines"] if line["side"] == "credit"), Decimal("0"))
    if debits != credits:
        raise SystemExit(f"journal example is not balanced: debit={debits} credit={credits}")
    if journal["status"] == "published" and not journal["audit_event_id"]:
        raise SystemExit("published journal must have audit_event_id")

    batch = load_json(EXAMPLES / "import-batch.example.json")
    if Decimal(batch["summary"]["debit_total"]) != Decimal(batch["summary"]["credit_total"]):
        raise SystemExit("import example must have balanced totals")
    if batch["mode"] == "dry_run" and batch["status"] == "published":
        raise SystemExit("dry_run batch cannot be published")

    case = load_json(EXAMPLES / "reconciliation-case.example.json")
    if case["status"] == "approved" and not (case.get("selected_candidate_id") and case.get("approved_by") and case.get("audit_event_id")):
        raise SystemExit("approved reconciliation case requires selected_candidate_id, approved_by and audit_event_id")

    close_run = load_json(EXAMPLES / "close-run.example.json")
    if close_run["status"] == "closed":
        blocking_pending = [item for item in close_run["checklist"] if item["blocking"] and item["status"] not in {"completed", "not_applicable"}]
        if blocking_pending:
            raise SystemExit("closed close_run contains blocking incomplete checklist items")
        if not close_run["snapshot_ref"] or not close_run["evidence_package_ref"]:
            raise SystemExit("closed close_run must have snapshot and evidence package")

    request = load_json(EXAMPLES / "document-request.example.json")
    if request["status"] == "confirmed" and not (request["document_id"] and request["confirmed_by"]):
        raise SystemExit("confirmed document request requires document_id and confirmed_by")
    if request["status"] == "cancelled" and not request["cancel_reason"]:
        raise SystemExit("cancelled document request requires cancel_reason")

    exported = load_json(EXAMPLES / "export-package.example.json")
    canonical = json.dumps(
        {key: value for key, value in exported.items() if key != "sha256"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if exported["sha256"] != hashlib.sha256(canonical.encode("utf-8")).hexdigest():
        raise SystemExit("export example sha256 does not match the canonical payload")
    if Decimal(exported["trial_balance"]["debit_total"]) != Decimal(exported["trial_balance"]["credit_total"]):
        raise SystemExit("export example trial balance is not balanced")

    obligation = load_json(EXAMPLES / "regulatory-obligation.example.json")
    if obligation["status"] == "accepted" and not any(t["status"] == "accepted" for t in obligation["transmissions"]):
        raise SystemExit("accepted obligation must have an accepted transmission")

    config = yaml.safe_load((ROOT / "configs/product.yaml").read_text(encoding="utf-8"))
    checks = {
        "balanced_journal": config["ledger"]["require_balanced_journal"] is True,
        "immutable_published": config["ledger"]["published_journal_immutable"] is True,
        "no_direct_db_writes": config["ledger"]["allow_direct_database_writes"] is False,
        "human_reconciliation": config["reconciliation"]["human_approval_required"] is True,
        "no_ai_publish": config["security"]["ai_can_publish_journal"] is False,
        "no_ai_transmit": config["security"]["ai_can_transmit_obligation"] is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("unsafe config invariants: " + ", ".join(failed))

    examples_text = " ".join(path.read_text(encoding="utf-8") for path in EXAMPLES.glob("*.json")).lower()
    for marker in ("access_token", "refresh_token", "private_key", "client_secret", "password"):
        if marker in examples_text:
            raise SystemExit(f"example contains possible secret field: {marker}")

    print(f"OK: {len(schemas)} JSON schemas, fixtures and accounting invariants are valid")


if __name__ == "__main__":
    main()
