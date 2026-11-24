"""Polish public holidays (days off work), computed without dependencies."""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


def easter_sunday(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


@lru_cache(maxsize=16)
def holidays(year: int) -> dict[date, str]:
    """Public holidays in Poland for a year, date -> Polish name."""
    easter = easter_sunday(year)
    days = {
        date(year, 1, 1): "Nowy Rok",
        date(year, 1, 6): "Trzech Króli",
        easter: "Wielkanoc",
        easter + timedelta(days=1): "Poniedziałek Wielkanocny",
        date(year, 5, 1): "Święto Pracy",
        date(year, 5, 3): "Święto Konstytucji 3 Maja",
        easter + timedelta(days=49): "Zielone Świątki",
        easter + timedelta(days=60): "Boże Ciało",
        date(year, 8, 15): "Wniebowzięcie NMP",
        date(year, 11, 1): "Wszystkich Świętych",
        date(year, 11, 11): "Święto Niepodległości",
        date(year, 12, 25): "Boże Narodzenie",
        date(year, 12, 26): "Drugi dzień Bożego Narodzenia",
    }
    if year >= 2025:  # Wigilia is a day off since 2025
        days[date(year, 12, 24)] = "Wigilia"
    return days


def holiday_name(day: date) -> str | None:
    """Name of the holiday on a day, or None."""
    return holidays(day.year).get(day)


def next_working_day(day: date) -> date:
    """The first day after `day` that is neither a Sunday nor a holiday."""
    nxt = day + timedelta(days=1)
    while nxt.weekday() == 6 or holiday_name(nxt):
        nxt += timedelta(days=1)
    return nxt
