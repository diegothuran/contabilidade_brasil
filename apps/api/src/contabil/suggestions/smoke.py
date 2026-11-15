"""Chamada real ao modelo com dados fictícios fixos (ADR 035).

Uso manual, só com autorização do usuário para o gasto: `python -m contabil.suggestions.smoke`.
Imprime refs, códigos, confiança, stop_reason e tokens; nunca o prompt, a justificativa ou a chave.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

from contabil.platform.settings import get_settings
from contabil.suggestions.model import AnthropicModelClient, build_prompt, validate_picks

CHART = [
    ("1.1.02", "Bancos", "asset"),
    ("2.1.01", "Fornecedores", "liability"),
    ("3.1.01", "Receita de serviços", "revenue"),
    ("5.1.01", "Despesas de serviços", "expense"),
    ("5.1.02", "Tarifas bancárias", "expense"),
    ("5.1.03", "Aluguel", "expense"),
]
# Transações fictícias; o banco (1.1.02) fica fora do plano enviado, como no worker.
TRANSACTIONS = [
    ("t1", "outflow", "45.90", "TARIFA PACOTE SERVICOS"),
    ("t2", "outflow", "2500.00", "PAGAMENTO BOLETO ALUGUEL SALA"),
    ("t3", "inflow", "1200.00", "PIX RECEBIDO CLIENTE FICTICIO"),
]


def main() -> int:
    settings = get_settings()
    if not settings.claude_api_key:
        print("CLAUDE_API_KEY vazia: o smoke não roda sem a chave.", file=sys.stderr)
        return 2
    chart = [item for item in CHART if item[0] != "1.1.02"]
    system, user = build_prompt(chart, TRANSACTIONS)
    client = AnthropicModelClient(settings.claude_api_key, settings.suggestion_model)
    result = client.suggest(system=system, user=user)
    print(f"modelo={settings.suggestion_model} stop_reason={result.stop_reason} input_tokens={result.input_tokens} output_tokens={result.output_tokens}")
    if result.answer is None:
        print("sem resposta aproveitável")
        return 1
    accounts = {code: SimpleNamespace(code=code, active=True, postable=True) for code, _name, _kind in chart}
    refs = {ref: ref for ref, *_rest in TRANSACTIONS}
    picks = validate_picks(result.answer, refs, accounts)
    for ref, account, confidence, _justification in picks:
        print(f"{ref} -> {account.code} ({confidence})")
    print(f"válidas={len(picks)} recebidas={len(result.answer.picks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
