from __future__ import annotations

from datetime import date

from sqlalchemy import select

from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.tables import ClientSubmission, DocumentRequest, DocumentRequestComment, DocumentRequestFile, LegalEntity


class _FakeDirectory:
    def create_test_login(self, username: str, email: str, tenant_id: str, temporary_password: str) -> bool:
        del username, email, tenant_id, temporary_password
        return True


def test_simulated_round_follows_each_persona_once(world):
    del world
    from contabil.pilot_round import prepare_round
    from contabil.pilot_samples import load_samples
    from contabil.pilot_simulation import MARK, simulate_round

    load_samples("tenant_demo")
    today = date.today()
    prepare_round("tenant_demo", _FakeDirectory(), today)  # type: ignore[arg-type]
    first = simulate_round("tenant_demo", today)
    assert first.notes == []
    assert {item.persona for item in first.clients} == {
        "Pontual", "Troca o arquivo", "Pergunta antes de enviar", "Não responde", "Manda pelo envio avulso",
    }
    assert not any(item.skipped for item in first.clients if item.persona != "Não responde")

    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        rows = session.execute(
            select(LegalEntity.name, DocumentRequest)
            .join(LegalEntity, LegalEntity.id == DocumentRequest.legal_entity_id)
            .where(DocumentRequest.tenant_id == "tenant_demo", DocumentRequest.title.like("Rodada:%"))
        ).all()
        status: dict[str, list[str]] = {}
        for name, row in rows:
            status.setdefault(name.split()[0], []).append(row.status)
        assert sorted(status["Padaria"]) == ["confirmed", "confirmed"]
        assert sorted(status["Studio"]) == ["confirmed", "confirmed"]
        assert sorted(status["Comercial"]) == ["open", "received"]
        assert sorted(status["Ateliê"]) == ["open", "open"]
        assert sorted(status["Transportes"]) == ["cancelled", "confirmed", "confirmed"]
        returned = session.scalars(
            select(DocumentRequestFile.returned_reason).where(DocumentRequestFile.tenant_id == "tenant_demo", DocumentRequestFile.state == "returned")
        ).all()
        assert any(reason and reason.startswith(MARK) for reason in returned)
        comments = session.scalars(select(DocumentRequestComment.author_kind).where(DocumentRequestComment.body.startswith(MARK))).all()
        assert {"client", "office"} <= set(comments)
        assert session.scalar(select(ClientSubmission.status).where(ClientSubmission.note.startswith(MARK))) == "classified"
    finally:
        session.close()

    second = simulate_round("tenant_demo", today)
    assert all(item.skipped or item.steps_done == 0 for item in second.clients)
