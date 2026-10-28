from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# Brasília não tem horário de verão desde 2019; prazo e lembrete são lidos nesse fuso.
BRASILIA = timezone(timedelta(hours=-3))


def brasilia_today(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(BRASILIA).date()
