# =========================================================
# FILE: app/utils/datetime_utils.py
# =========================================================

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional


UTC = timezone.utc


def utc_now() -> datetime:
    """
    Returns timezone-aware UTC datetime.
    """
    return datetime.now(UTC)


def utc_iso() -> str:
    """
    Returns ISO8601 UTC timestamp.
    """
    return utc_now().isoformat()


def ensure_utc(
    value: Optional[datetime],
) -> Optional[datetime]:
    """
    Converts datetime to UTC-aware datetime.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def add_minutes(
    value: datetime,
    minutes: int,
) -> datetime:
    return ensure_utc(value) + timedelta(minutes=minutes)


def add_hours(
    value: datetime,
    hours: int,
) -> datetime:
    return ensure_utc(value) + timedelta(hours=hours)


def add_days(
    value: datetime,
    days: int,
) -> datetime:
    return ensure_utc(value) + timedelta(days=days)


def is_expired(
    value: Optional[datetime],
) -> bool:
    if value is None:
        return True

    return ensure_utc(value) < utc_now()


def datetime_to_timestamp(
    value: datetime,
) -> int:
    return int(ensure_utc(value).timestamp())


def timestamp_to_datetime(
    value: int,
) -> datetime:
    return datetime.fromtimestamp(value, tz=UTC)