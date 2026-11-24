from __future__ import annotations

from pathlib import Path

import pytest

from contabil.platform import conferences
from contabil.platform.conferences import Thresholds, load_thresholds
from contabil.platform.settings import Settings, get_settings


@pytest.fixture
def clean_caches():
    get_settings.cache_clear()
    load_thresholds.cache_clear()
    yield
    get_settings.cache_clear()
    load_thresholds.cache_clear()


def test_load_thresholds_reads_versioned_file(clean_caches, monkeypatch):
    # No repositório vale o caminho padrão; na imagem não há repositório e vale o CONFIGS_DIR do Dockerfile.
    if (Path(conferences.__file__).resolve().parents[5] / "configs" / "conferencias.yaml").exists():
        monkeypatch.delenv("CONFIGS_DIR", raising=False)
    thresholds = load_thresholds()
    assert isinstance(thresholds, Thresholds)
    assert thresholds.version == "2026.11-provisorio"
    assert thresholds.duplicate_payment_window_days == 3
    assert thresholds.own_transfer_window_days == 2
    assert thresholds.idle_balance_months == 3


def test_load_thresholds_rejects_missing_key(clean_caches, monkeypatch, tmp_path):
    (tmp_path / "conferencias.yaml").write_text(
        "version: teste\nduplicate_payment_window_days: 3\nown_transfer_window_days: 2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIGS_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="idle_balance_months"):
        load_thresholds()


def test_settings_suggestion_defaults(monkeypatch):
    for name in ("CLAUDE_API_KEY", "SUGGESTION_MODEL", "SUGGESTION_DAILY_LIMIT"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.suggestion_model == "claude-haiku-5-5"
    assert settings.suggestion_daily_limit == 500
    assert settings.claude_api_key == ""
