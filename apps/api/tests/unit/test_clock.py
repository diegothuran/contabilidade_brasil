from __future__ import annotations

from datetime import date, datetime, timezone

from contabil.identity.notices import reminder_kind
from contabil.platform.clock import brasilia_today


def test_late_evening_in_brasilia_is_still_the_same_day() -> None:
    # 22h de 27/10 em Brasília já é 28/10 em UTC.
    late = datetime(2026, 10, 28, 1, tzinfo=timezone.utc)
    assert brasilia_today(late) == date(2026, 10, 27)


def test_reminder_three_days_before_uses_the_brasilia_day() -> None:
    today = brasilia_today(datetime(2026, 10, 28, 1, tzinfo=timezone.utc))
    assert reminder_kind(date(2026, 10, 30), today) == "due_soon"
    assert reminder_kind(date(2026, 10, 31), today) is None
