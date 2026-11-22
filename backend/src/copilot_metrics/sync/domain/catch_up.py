"""Which days still need fetching, and grouping them per month."""

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta


def days_to_catch_up(window: Iterable[date], last_synced: Mapping[date, datetime], settle_days: int) -> list[date]:
    """Days in ``window`` still to fetch, newest first (recent data matters most).

    A day counts as done once it was synced ``settle_days`` or more after it - the periodic
    jobs re-fetch that many recent days, so GitHub's late corrections are in by then. A day
    synced earlier (say the worker stopped the same afternoon) is fetched again.
    """
    return sorted(
        (
            day
            for day in window
            if (synced := last_synced.get(day)) is None or synced.date() < day + timedelta(days=settle_days)
        ),
        reverse=True,
    )


def by_month(days: Iterable[date]) -> list[list[date]]:
    """``days`` split into one list per calendar month, keeping their order (months by first appearance)."""
    months: dict[date, list[date]] = {}
    for day in days:
        months.setdefault(day.replace(day=1), []).append(day)
    return list(months.values())
