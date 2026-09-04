"""Recurring schedule math in a fixed wall-clock timezone (default Europe/Moscow).

Russia has no daylight-saving shifts, so wall-clock times map to UTC with a
constant offset — schedules never drift by an hour.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

RepeatMode = Literal["once", "hourly", "daily", "weekly"]

DEFAULT_TIMEZONE = "Europe/Moscow"

__all__ = ["DEFAULT_TIMEZONE", "RepeatMode", "first_run", "next_run", "resolve_zone"]


def resolve_zone(name: str) -> ZoneInfo:
    """Return the zone or raise ValueError for unknown names (mapped to 422)."""
    try:
        return ZoneInfo(name)
    except Exception as err:
        raise ValueError(f"Unknown timezone: {name!r}") from err


def _wall_time(anchor: datetime, tz: ZoneInfo) -> tuple[int, int]:
    local = anchor.astimezone(tz)
    return local.hour, local.minute


def _at(local_day: date, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    return datetime(
        local_day.year, local_day.month, local_day.day, hour, minute, tzinfo=tz
    ).astimezone(UTC)


def _first_daily(requested: datetime, anchor: datetime, tz: ZoneInfo) -> datetime:
    hour, minute = _wall_time(anchor, tz)
    candidate = _at(requested.astimezone(tz).date(), hour, minute, tz)
    if candidate < requested:
        candidate = _at(
            (requested.astimezone(tz) + timedelta(days=1)).date(), hour, minute, tz
        )
    return candidate


def _next_daily(after: datetime, anchor: datetime, tz: ZoneInfo) -> datetime:
    hour, minute = _wall_time(anchor, tz)
    candidate = _at(after.astimezone(tz).date(), hour, minute, tz)
    if candidate <= after:
        candidate = _at(
            (after.astimezone(tz) + timedelta(days=1)).date(), hour, minute, tz
        )
    return candidate


def _first_weekly(
    requested: datetime, anchor: datetime, days: list[int], tz: ZoneInfo
) -> datetime:
    hour, minute = _wall_time(anchor, tz)
    start = requested.astimezone(tz)
    for offset in range(8):
        day = (start + timedelta(days=offset)).date()
        if day.weekday() in days:
            candidate = _at(day, hour, minute, tz)
            if candidate >= requested:
                return candidate
    raise AssertionError("unreachable: 8-day scan always hits a selected weekday")


def _next_weekly(
    after: datetime, anchor: datetime, days: list[int], tz: ZoneInfo
) -> datetime:
    hour, minute = _wall_time(anchor, tz)
    start = after.astimezone(tz)
    for offset in range(8):
        day = (start + timedelta(days=offset)).date()
        if day.weekday() in days:
            candidate = _at(day, hour, minute, tz)
            if candidate > after:
                return candidate
    raise AssertionError("unreachable: 8-day scan always hits a selected weekday")


def _next_hourly(
    after: datetime, anchor: datetime, interval_hours: int
) -> datetime:
    if after < anchor:
        return anchor
    step = timedelta(hours=interval_hours)
    missed = (after - anchor) // step + 1
    return anchor + missed * step


def first_run(
    requested: datetime,
    *,
    repeat: RepeatMode,
    anchor: datetime,
    interval_hours: int | None = None,
    days: list[int] | None = None,
    tz: ZoneInfo | None = None,
) -> datetime:
    """First occurrence at or after ``requested`` (``requested`` itself if once)."""
    zone = tz or ZoneInfo(DEFAULT_TIMEZONE)
    if repeat == "once":
        return requested
    if repeat == "hourly":
        assert interval_hours is not None
        return requested if requested <= anchor else _next_hourly(requested, anchor, interval_hours)
    if repeat == "daily":
        return _first_daily(requested, anchor, zone)
    assert days is not None
    return _first_weekly(requested, anchor, days, zone)


def next_run(
    after: datetime,
    *,
    anchor: datetime,
    repeat: RepeatMode,
    interval_hours: int | None = None,
    days: list[int] | None = None,
    tz: ZoneInfo | None = None,
) -> datetime:
    """Next occurrence strictly after ``after``; never called for ``once``."""
    zone = tz or ZoneInfo(DEFAULT_TIMEZONE)
    if repeat == "hourly":
        assert interval_hours is not None
        return _next_hourly(after, anchor, interval_hours)
    if repeat == "daily":
        return _next_daily(after, anchor, zone)
    assert days is not None
    return _next_weekly(after, anchor, days, zone)
