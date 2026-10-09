# ai-generated: 90% - assistant drafted the SLA clocks from API.md section 4 and checked them on vectors T1-T8
"""Instants and the two SLA clocks (wall clock and Europe/Warsaw business hours)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
UTC = timezone.utc

# Minutes. P1 is wall-clock under C1=wallclock; P2-P4 are always business hours.
TARGETS_MINUTES = {
    "P1": (15, 4 * 60),
    "P2": (60, 8 * 60),
    "P3": (4 * 60, 24 * 60),
    "P4": (8 * 60, 72 * 60),
}


def parse_instant(value: str) -> datetime:
    """Parse an RFC 3339 instant that carries an offset. Naive timestamps are rejected."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp is required")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("timestamp is not RFC 3339") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no offset")
    return parsed.astimezone(UTC)


def format_instant(moment: datetime) -> str:
    """UTC instant with a Z suffix. Whole seconds stay whole; fractions are kept."""
    moment = moment.astimezone(UTC)
    if moment.microsecond == 0:
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    fraction = f"{moment.microsecond:06d}".rstrip("0")
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + fraction + "Z"


def _opening(day) -> datetime:
    return datetime(day.year, day.month, day.day, 8, 0, 0, tzinfo=WARSAW)


def _next_business_day(day):
    nxt = day + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def align_to_business(moment: datetime) -> datetime:
    """Move forward to the next instant inside [Mon-Fri 08:00, 16:00) Europe/Warsaw."""
    local = moment.astimezone(WARSAW)
    opening = local.replace(hour=8, minute=0, second=0, microsecond=0)
    closing = local.replace(hour=16, minute=0, second=0, microsecond=0)
    if local.weekday() < 5 and opening <= local < closing:
        return local
    if local.weekday() < 5 and local < opening:
        return opening
    return _opening(_next_business_day(local.date()))


def add_business_minutes(start: datetime, minutes: int) -> datetime:
    """Consume `minutes` only inside business windows. A target that lands on 16:00 stays at 16:00."""
    cursor = align_to_business(start)
    remaining = minutes * 60  # seconds, so the tie at closing is exact
    while remaining > 0:
        closing = cursor.replace(hour=16, minute=0, second=0, microsecond=0)
        available = int((closing - cursor).total_seconds())
        if remaining <= available:
            cursor = cursor + timedelta(seconds=remaining)
            remaining = 0
        else:
            remaining -= available
            cursor = _opening(_next_business_day(cursor.date()))
    return cursor.astimezone(UTC)


def add_wall_minutes(start: datetime, minutes: int) -> datetime:
    return (start.astimezone(UTC) + timedelta(minutes=minutes)).astimezone(UTC)


def in_business_hours(moment: datetime) -> bool:
    local = moment.astimezone(WARSAW)
    if local.weekday() >= 5:
        return False
    opening = local.replace(hour=8, minute=0, second=0, microsecond=0)
    closing = local.replace(hour=16, minute=0, second=0, microsecond=0)
    return opening <= local < closing


def due_instants(created_at: datetime, priority: str, p1_wallclock: bool) -> tuple[datetime, datetime, bool]:
    """Return ack due, resolve due, and whether the resolution target uses the business-hours clock."""
    ack_min, resolve_min = TARGETS_MINUTES[priority]
    use_business = not (priority == "P1" and p1_wallclock)
    if use_business:
        return (
            add_business_minutes(created_at, ack_min),
            add_business_minutes(created_at, resolve_min),
            True,
        )
    return (
        add_wall_minutes(created_at, ack_min),
        add_wall_minutes(created_at, resolve_min),
        False,
    )
