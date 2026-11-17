"""Small datetime helpers shared by investigation tools."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def parse_iso(value: str | None, *, default: datetime | None = None) -> datetime:
    """Parse an ISO-8601 timestamp, accepting a trailing Z."""
    if value is None:
        if default is not None:
            return default
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def default_window(
    start_time: str | None,
    end_time: str | None,
    *,
    hours: int = 1,
) -> tuple[datetime, datetime]:
    """Return a (start, end) window, defaulting to the last ``hours`` hours."""
    now = datetime.now(UTC)
    start = parse_iso(start_time, default=now - timedelta(hours=hours))
    end = parse_iso(end_time, default=now)
    return start, end
