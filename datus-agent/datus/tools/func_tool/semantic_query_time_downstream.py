"""Downstream query-time normalization for semantic metric requests."""

from __future__ import annotations

import re
from calendar import monthrange
from collections.abc import Callable
from datetime import date, timedelta

from datus.tools.func_tool.base import normalize_null
from datus.utils.time_utils import get_default_current_date

_RELATIVE_QUERY_TIME_RE = re.compile(r"^-(\d+)([dwmy])$", re.IGNORECASE)


def normalize_query_time_range(
    time_start: str | None,
    time_end: str | None,
    reference_date_provider: Callable[[], str | None] | None,
) -> tuple[str | None, str | None]:
    relative_time_values = (time_start, time_end)
    needs_reference_date = any(
        isinstance(value, str)
        and (value.strip().lower() == "now" or _RELATIVE_QUERY_TIME_RE.fullmatch(value.strip()) is not None)
        for value in relative_time_values
    )
    reference_date = _query_time_reference_date(reference_date_provider) if needs_reference_date else None
    return (
        _normalize_query_time(time_start, label="time_start", reference_date=reference_date),
        _normalize_query_time(time_end, label="time_end", reference_date=reference_date),
    )


def _query_time_reference_date(reference_date_provider: Callable[[], str | None] | None) -> date:
    configured_date = reference_date_provider() if reference_date_provider else None
    reference_text = get_default_current_date(configured_date)
    try:
        return date.fromisoformat(reference_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"query_metrics reference date must use YYYY-MM-DD format: {reference_text!r}") from exc


def _normalize_query_time(
    value: str | None,
    *,
    label: str,
    reference_date: date | None,
) -> str | None:
    value = normalize_null(value)
    if value is None or not isinstance(value, str):
        return value

    text = value.strip()
    if text.lower() == "now":
        return (reference_date or _query_time_reference_date(None)).isoformat()

    match = _RELATIVE_QUERY_TIME_RE.fullmatch(text)
    if match:
        count = int(match.group(1))
        unit = match.group(2).lower()
        reference_date = reference_date or _query_time_reference_date(None)
        if unit == "d":
            resolved = reference_date - timedelta(days=count)
        elif unit == "w":
            resolved = reference_date - timedelta(weeks=count)
        elif unit == "m":
            resolved = _shift_calendar_months(reference_date, -count)
        else:
            resolved = _shift_calendar_months(reference_date, -12 * count)
        return resolved.isoformat()

    if text.startswith("-"):
        raise ValueError(
            f"query_metrics {label} must be an ISO date/timestamp or a relative value "
            "like '-7d', '-2w', '-3m', or '-1y'."
        )
    return text


def _shift_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
