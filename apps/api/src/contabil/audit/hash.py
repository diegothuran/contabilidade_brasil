from __future__ import annotations

import hashlib
import json


def canonical_payload(
    *,
    schema_version: str,
    event_id: str,
    tenant_id: str,
    event_type: str,
    actor_kind: str,
    actor_ref: str,
    occurred_at: str,
    target_type: str,
    target_ref: str,
    reason: str | None,
    metadata: dict,
) -> str:
    body = {
        "schema_version": schema_version,
        "event_id": event_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "actor_kind": actor_kind,
        "actor_ref": actor_ref,
        "occurred_at": occurred_at,
        "target_type": target_type,
        "target_ref": target_ref,
        "reason": reason,
        "metadata": metadata or {},
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def chain_hash(previous: str | None, canonical: str) -> str:
    return hashlib.sha256(((previous or "") + canonical).encode("utf-8")).hexdigest()
