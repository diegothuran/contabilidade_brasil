from __future__ import annotations

import pytest

from contabil.document_requests.service import cancel_reason_error, next_status
from contabil.platform.errors import DomainError


def test_request_moves_from_open_to_confirmed_or_cancelled() -> None:
    assert next_status("open", "receive") == "received"
    assert next_status("received", "confirm") == "confirmed"
    assert next_status("open", "cancel") == "cancelled"
    assert next_status("received", "cancel") == "cancelled"


def test_confirm_before_the_file_is_rejected() -> None:
    with pytest.raises(DomainError) as caught:
        next_status("open", "confirm")
    assert caught.value.status_code == 409


def test_finished_request_stays_finished() -> None:
    with pytest.raises(DomainError):
        next_status("confirmed", "cancel")
    with pytest.raises(DomainError):
        next_status("cancelled", "receive")


def test_cancel_needs_a_reason() -> None:
    assert cancel_reason_error("curto")
    assert cancel_reason_error("  curto  ")
    assert cancel_reason_error("Pedido feito na competência errada.") is None
