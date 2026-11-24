"""Chamada real ao modelo com um pacote do mês fictício e fixo (ADR 036).

Uso manual, só com autorização do usuário para o gasto: `python -m contabil.ai_reviews.smoke`.
O pacote traz dois problemas plantados: a despesa de serviços triplicou e o lucro não aparece no banco.
Imprime relevância, categoria, título e evidências dos pontos válidos, stop_reason e tokens;
nunca a explicação inteira ou a chave.
"""
from __future__ import annotations

import sys
from decimal import Decimal

from contabil.ai_reviews.model import AnthropicReviewClient, build_review_prompt, validate_points
from contabil.ai_reviews.packet import AccountLine, compose_packet, packet_refs
from contabil.platform.settings import get_settings


def _line(code: str, name: str, kind: str, opening: str, debit: str, credit: str, previous: tuple[str, str, str]) -> AccountLine:
    closing = Decimal(opening) + Decimal(debit) - Decimal(credit)
    return AccountLine(code, name, kind, Decimal(opening), Decimal(debit), Decimal(credit), closing, tuple(Decimal(v) for v in previous))


def fictitious_packet() -> dict:
    return compose_packet(
        competence="2026-11",
        period_status="open",
        accounts=[
            _line("1.1.02", "Bancos", "asset", "18000.00", "9000.00", "12600.00", ("1500.00", "2100.00", "1800.00")),
            _line("1.1.03", "Clientes a receber", "asset", "2000.00", "6000.00", "0.00", ("0.00", "500.00", "-500.00")),
            _line("2.1.01", "Fornecedores", "liability", "-3000.00", "3000.00", "3300.00", ("200.00", "-100.00", "0.00")),
            _line("4.1.01", "Receita de serviços", "revenue", "-30000.00", "0.00", "15000.00", ("-9500.00", "-10200.00", "-9800.00")),
            _line("5.1.01", "Despesas de serviços", "expense", "4200.00", "4500.00", "0.00", ("1400.00", "1350.00", "1450.00")),
            _line("5.1.02", "Tarifas bancárias", "expense", "300.00", "100.00", "0.00", ("95.00", "105.00", "100.00")),
            _line("5.1.03", "Aluguel", "expense", "7500.00", "2500.00", "0.00", ("2500.00", "2500.00", "2500.00")),
        ],
        indicators={
            "receita": ("15000.00", ["9500.00", "10200.00", "9800.00"]),
            "despesa": ("7100.00", ["3995.00", "3955.00", "4050.00"]),
            "resultado": ("7900.00", ["5505.00", "6245.00", "5750.00"]),
            "dinheiro_em_conta": ("14400.00", []),
        },
        checks=[],
        pending={
            "lancamentos_rascunho": 1,
            "lancamentos_pendentes": 0,
            "lancamentos_aprovados_nao_publicados": 0,
            "casos_conciliacao_pendentes": 3,
            "pedidos_documento_abertos": 1,
            "alertas_extrato": 0,
        },
    )


def main() -> int:
    settings = get_settings()
    if not settings.claude_api_key:
        print("CLAUDE_API_KEY vazia: o smoke não roda sem a chave.", file=sys.stderr)
        return 2
    packet = fictitious_packet()
    system, user = build_review_prompt(packet)
    client = AnthropicReviewClient(settings.claude_api_key, settings.review_model)
    result = client.review(system=system, user=user)
    print(f"modelo={settings.review_model} stop_reason={result.stop_reason} input_tokens={result.input_tokens} output_tokens={result.output_tokens}")
    if result.answer is None:
        print("sem resposta aproveitável")
        return 1
    points = validate_points(result.answer, packet_refs(packet))
    for index, point in enumerate(points, start=1):
        print(f"{index}. [{point.relevance}/{point.category}] {point.title} -> {', '.join(point.evidence)}")
    print(f"válidos={len(points)} recebidos={len(result.answer.pontos)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
