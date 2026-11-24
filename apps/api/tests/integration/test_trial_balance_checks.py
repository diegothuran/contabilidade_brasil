from __future__ import annotations

from tests.integration.test_phase_a import _auth, _journal_body, _publish

URL = "/v1/periods/le_test-2026-09/trial-balance-checks"


def test_checks_route_flags_inverted_asset(client, tokens, world):
    del world
    body = _journal_body(
        lines=[
            {"account_id": "le_test-5.1.01", "side": "debit", "amount": "10.00", "description": "Débito"},
            {"account_id": "le_test-1.1.02", "side": "credit", "amount": "10.00", "description": "Crédito"},
        ]
    )
    _publish(client, tokens, body)
    response = client.get(URL, headers=_auth(tokens["viewer"]))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["period_id"] == "le_test-2026-09"
    assert payload["rule_version"]
    inverted = [i for i in payload["items"] if i["kind"] == "inverted_balance" and i["code"] == "1.1.02"]
    assert len(inverted) == 1
    assert inverted[0]["amount"].startswith("-")


def test_checks_route_other_tenant_404(client, tokens, world):
    del world
    assert client.get(URL, headers=_auth(tokens["outsider"])).status_code == 404


def test_checks_route_client_forbidden(client, tokens, world):
    del world
    assert client.get(URL, headers=_auth(tokens["cliente"])).status_code == 403
