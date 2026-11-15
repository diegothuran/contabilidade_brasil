"""Os testes nunca alcançam a API da Anthropic, mesmo com chave no ambiente."""
from __future__ import annotations

import pytest

from contabil.platform.settings import get_settings
from contabil.suggestions.model import AnthropicModelClient
from tests.conftest import BLOCKED


def test_settings_start_without_key():
    get_settings.cache_clear()
    try:
        assert get_settings().claude_api_key == ""
    finally:
        get_settings.cache_clear()


def test_real_client_cannot_be_built_in_tests():
    with pytest.raises(RuntimeError, match=BLOCKED):
        AnthropicModelClient("chave-de-teste", "claude-haiku-5-5")
