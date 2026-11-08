#!/usr/bin/env python3
"""ISO 8601 week-date codes: `w##DDD` labels, `YYYY-Www` week keys, the 13-week quarter, workday spans.

The single owner of week codes for GBOGEB (AGENTS.md "Metric ownership"). Import it; do not copy it.
`actions_metrics.iso_week()` delegates to `iso_week_key()` here, and from another tree you load this
file with `importlib.util.spec_from_file_location`, as `actions_metrics._load()` does. Mermaid schedule
patterns that use these codes are in `WDDD_WEEK_CODES.md` next to this file.

Codes
  * `2026-w46MON` is the canonical form: ISO year, ISO week, three-letter ISO weekday.
  * `w46MON` is a display label only. ISO week 1 can start in December (`2026-w01MON` is 2025-12-29)
    and week 53 exists only in 53-week years, so a bare label needs the ISO year passed in.
  * `2026-W46` (`iso_week_key`) is the week key the hub's Actions metrics already use, so the two join.

The 13-week quarter (w01-w13, w14-w26, w27-w39, w40-w52, with w53 folded into Q4) is a project
convention, not part of ISO 8601, hence the name `quarter_13w`.

Standard library only (JADE floor: Python 3.12, `tests/test_jade_build_contract.py`).
User-approved for global roll-out on 2026-11-08 from the merged B1/B2 handover of that day.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

DAYS_3L = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_CODE = re.compile(r"^(?:(?P<year>[0-9]{4})-)?[wW](?P<week>[0-9]{2})(?P<day>[A-Za-z]{3})$")


def weeks_in_iso_year(iso_year: int) -> int:
    """52 or 53. 28 December always falls in the last ISO week of its ISO year."""
    return date(iso_year, 12, 28).isocalendar()[1]


def to_w_code(d: date, with_year: bool = False) -> str:
    """date(2026, 11, 9) -> 'w46MON', or '2026-w46MON' with with_year=True."""
    iso_year, week, weekday = d.isocalendar()[:3]
    code = f"w{week:02d}{DAYS_3L[weekday - 1]}"
    return f"{iso_year}-{code}" if with_year else code


def from_w_code(code: str, iso_year: int | None = None) -> date:
    """'2026-w46MON', or 'w46MON' with iso_year=2026 -> date(2026, 11, 9).

    Raises ValueError for a malformed code, a bare code without iso_year, a year that conflicts
    with iso_year, an unknown weekday, or a week the ISO year does not have.
    """
    m = _CODE.match(code.strip())
    if not m:
        raise ValueError(f"not a w##DDD code: {code!r}")
    year = int(m["year"]) if m["year"] else iso_year
    if year is None:
        raise ValueError(f"{code!r} has no ISO year; pass iso_year or use the 'YYYY-w##DDD' form")
    if m["year"] and iso_year is not None and iso_year != year:
        raise ValueError(f"{code!r} conflicts with iso_year={iso_year}")
    day = m["day"].upper()
    if day not in DAYS_3L:
        raise ValueError(f"unknown day {day!r} in {code!r}")
    week = int(m["week"])
    if not 1 <= week <= weeks_in_iso_year(year):
        raise ValueError(f"ISO year {year} has no week {week:02d}")
    return date.fromisocalendar(year, week, DAYS_3L.index(day) + 1)


def iso_week_key(d: date) -> str:
    """date(2026, 11, 9) -> '2026-W46'. Accepts a datetime too (its own calendar date is used)."""
    iso_year, week = d.isocalendar()[:2]
    return f"{iso_year}-W{week:02d}"


def quarter_13w(week: int) -> str:
    """Project convention: w01-w13 Q1, w14-w26 Q2, w27-w39 Q3, w40-w52 and w53 Q4."""
    if not 1 <= week <= 53:
        raise ValueError(f"week {week} out of range")
    return f"Q{min(4, (week - 1) // 13 + 1)}"


def add_workdays(start: date, n: int, holidays: frozenset[date] = frozenset()) -> date:
    """Last day of an n-workday span that starts on `start`.

    Same rule as a Mermaid gantt task `<start>, <n>d` under `excludes weekends, <holidays>`:
    Saturdays, Sundays and the given holidays are skipped and not counted.
    """
    if n < 1:
        raise ValueError(f"a span needs at least one workday, got {n}")
    d, left = start, n
    while True:
        if d.weekday() < 5 and d not in holidays:
            left -= 1
            if left == 0:
                return d
        d += timedelta(days=1)
