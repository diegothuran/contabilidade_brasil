from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from contabil.pilot_report import request_cycles, summarize

_TODAY = date(2026, 10, 27)


def _request(request_id: str, status: str, due_on: date, received_by: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=request_id,
        title=f"Pedido {request_id}",
        due_on=due_on,
        status=status,
        received_by=received_by,
        company="Padaria Aurora (teste)",
        period="10/2026",
    )


def _event(request_id: str, action: str, moment: datetime, actor: str = "preparer") -> SimpleNamespace:
    return SimpleNamespace(target_ref=request_id, occurred_at=moment, actor_ref=actor, details={"action": action})


def _at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


def _cycles() -> list[dict]:
    requests = [
        _request("cliente", "confirmed", date(2026, 10, 20), received_by="cliente-andamento"),
        _request("escritorio", "received", date(2026, 10, 5), received_by="preparer"),
        _request("vencido", "open", date(2026, 10, 20)),
        _request("futuro", "open", date(2026, 10, 31)),
        _request("cancelado", "cancelled", date(2026, 10, 20)),
    ]
    events = [
        _event("cliente", "document_request_opened", _at(1)),
        _event("cliente", "document_request_received", _at(4)),
        _event("cliente", "document_request_confirmed", _at(5)),
        _event("escritorio", "document_request_opened", _at(1)),
        _event("escritorio", "document_request_received", _at(10)),
        _event("vencido", "document_request_opened", _at(1)),
        _event("futuro", "document_request_opened", _at(1)),
        _event("cancelado", "document_request_opened", _at(1)),
        _event("cancelado", "document_request_cancelled", _at(2)),
    ]
    return request_cycles(requests, events, {"cliente-andamento"}, _TODAY)


def test_cycle_tells_who_sent_and_how_long_it_took() -> None:
    by_id = {item["pedido"]: item for item in _cycles()}
    client = by_id["Pedido cliente"]
    assert client["enviado_por"] == "cliente"
    assert client["dias_ate_receber"] == 3.0
    assert client["dias_ate_confirmar"] == 1.0
    assert client["no_prazo"] is True
    office = by_id["Pedido escritorio"]
    assert office["enviado_por"] == "escritorio"
    assert office["no_prazo"] is False
    assert office["dias_ate_confirmar"] is None


def test_open_request_is_late_only_after_the_due_date() -> None:
    by_id = {item["pedido"]: item for item in _cycles()}
    assert by_id["Pedido vencido"]["no_prazo"] is False
    assert by_id["Pedido futuro"]["no_prazo"] is None
    assert by_id["Pedido cancelado"]["no_prazo"] is None
    assert by_id["Pedido cancelado"]["encerrado_em"] == _at(2)


def test_due_date_is_read_in_brasilia_time() -> None:
    late_night = datetime(2026, 10, 21, 2, tzinfo=timezone.utc)
    cycles = request_cycles(
        [_request("noite", "received", date(2026, 10, 20), received_by="cliente-andamento")],
        [_event("noite", "document_request_received", late_night)],
        {"cliente-andamento"},
        _TODAY,
    )
    assert cycles[0]["no_prazo"] is True


def test_summary_counts_client_uploads_and_open_items() -> None:
    summary = summarize(_cycles())
    assert summary["pedidos"] == 5
    assert summary["enviados_pelo_cliente"] == 1
    assert summary["recebidos_no_prazo"] == "1/2"
    assert summary["mediana_dias_ate_receber"] == 6.0
    assert summary["mediana_dias_ate_confirmar"] == 1.0
    assert summary["abertos"] == 3
    assert summary["abertos_vencidos"] == 1


def test_cycle_counts_returns_and_conversation_by_side() -> None:
    cycles = request_cycles(
        [_request("refeito", "confirmed", date(2026, 10, 20), received_by="cliente-andamento")],
        [
            _event("refeito", "document_request_opened", _at(1)),
            _event("refeito", "document_request_received", _at(3), "cliente-andamento"),
            _event("refeito", "document_request_returned", _at(4), "approver"),
            _event("refeito", "document_request_commented", _at(4), "approver"),
            _event("refeito", "document_request_commented", _at(5), "cliente-andamento"),
            _event("refeito", "document_request_received", _at(6), "cliente-andamento"),
            _event("refeito", "document_request_confirmed", _at(7), "approver"),
        ],
        {"cliente-andamento"},
        _TODAY,
    )
    item = cycles[0]
    assert item["recebido_em"] == _at(3)
    assert item["devolucoes"] == 1
    assert item["comentarios_cliente"] == 1
    assert item["comentarios_escritorio"] == 1
    assert item["dias_ate_aceitar"] == 6.0
    summary = summarize(cycles, ["new", "classified", "discarded"])
    assert summary["pedidos_com_devolucao"] == 1
    assert summary["pedidos_com_conversa"] == 1
    assert summary["envios_sem_pedido"] == 3
    assert summary["envios_sem_pedido_classificados"] == 1


def test_summary_without_submissions_counts_zero() -> None:
    summary = summarize(_cycles())
    assert summary["pedidos_com_devolucao"] == 0
    assert summary["envios_sem_pedido"] == 0
