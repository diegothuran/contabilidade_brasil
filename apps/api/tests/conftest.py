"""Proteções comuns aos testes unitários e de integração.

Nenhum teste chama a API da Anthropic. A chave do ambiente (por exemplo, a do .env de quem
desenvolve, repassada pelo docker-compose) é apagada antes de qualquer Settings ser lido, e
o cliente real do SDK é trocado por um que recusa a construção. Teste que precisa de chave
usa um valor fictício via monkeypatch; teste que precisa de modelo injeta um cliente falso.

O outbox em processo fica desligado: um evento deixado por um teste não pode ser despachado
por uma thread em segundo plano entre um teste e outro, com outra configuração.
"""
from __future__ import annotations

import os

import pytest

os.environ["CLAUDE_API_KEY"] = ""
os.environ["OUTBOX_IN_PROCESS"] = "0"

BLOCKED = "Chamada real à API da Anthropic bloqueada nos testes."


class _BlockedAnthropic:
    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        raise RuntimeError(BLOCKED)


@pytest.fixture(autouse=True)
def _block_anthropic_network(monkeypatch):
    try:
        import anthropic
    except ImportError:
        return
    monkeypatch.setattr(anthropic, "Anthropic", _BlockedAnthropic)
