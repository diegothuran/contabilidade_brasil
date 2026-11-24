from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from contabil.platform.settings import get_settings

_KEYS = ("duplicate_payment_window_days", "own_transfer_window_days", "idle_balance_months")


@dataclass(frozen=True)
class Thresholds:
    version: str
    duplicate_payment_window_days: int
    own_transfer_window_days: int
    idle_balance_months: int


def _config_path() -> Path:
    configs_dir = get_settings().configs_dir
    if configs_dir:
        return Path(configs_dir) / "conferencias.yaml"
    return Path(__file__).resolve().parents[5] / "configs" / "conferencias.yaml"


@lru_cache
def load_thresholds() -> Thresholds:
    data = yaml.safe_load(_config_path().read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("conferencias.yaml precisa ser um mapa")
    for key in ("version", *_KEYS):
        if key not in data:
            raise ValueError(f"conferencias.yaml sem a chave {key}")
    values = {}
    for key in _KEYS:
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"conferencias.yaml: {key} precisa ser inteiro positivo")
        values[key] = value
    return Thresholds(version=str(data["version"]), **values)
