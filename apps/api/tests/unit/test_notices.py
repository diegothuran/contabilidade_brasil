from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from contabil.identity import notices
from contabil.identity.mailer import UnavailableMailer
from contabil.identity.notices import _send


class _FailingSession:
    def _fail(self, *args, **kwargs):
        raise AssertionError("sessão consultada")

    scalar = scalars = execute = add = _fail


def _no_directory():
    raise AssertionError("diretório consultado")


def test_send_skips_everything_when_mail_is_off(monkeypatch) -> None:
    monkeypatch.setattr(notices, "get_mailer", lambda: UnavailableMailer())
    monkeypatch.setattr(notices, "get_user_directory", _no_directory)
    row = SimpleNamespace(id="req_1", tenant_id="t", legal_entity_id="le", title="T", due_on=date(2026, 10, 20))

    assert _send(_FailingSession(), row, "overdue", date(2026, 10, 20)) is False
