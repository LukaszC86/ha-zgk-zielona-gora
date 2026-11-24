"""Turn one ZGK address record into pickup dates.

Pure Python, no Home Assistant imports, so it can be tested on its own.

A ZGK field holds one of:
- explicit dates: "13.01.2026, 27.01.2026, ..." (sometimes with a trailing note),
- a weekday for a weekly round: "środa", "poniedziałek, piątek" (typos happen:
  "czawartek", "CZWARTEK", "Piątek"),
- "sobota co dwa tygodnie, zgodnie z harmonogramem na odbiór odpadów z
  pojemnika": the same dates as the mixed-waste round,
- "BRAK", "-" or "": no collection.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from .const import (
    BIO,
    BULK,
    HOLIDAY_NEXT_DAY,
    HOLIDAY_SKIP,
    MIXED,
    SELECTIVE,
    WASTE_TYPES,
)
from .holidays_pl import holiday_name, next_working_day

DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\d)")
WORD_RE = re.compile(r"[a-z]+")

WEEKDAYS = {
    "poniedzialek": 0,
    "wtorek": 1,
    "sroda": 2,
    "czwartek": 3,
    "piatek": 4,
    "sobota": 5,
    "niedziela": 6,
}
WEEKDAY_NAMES = [
    "poniedziałek",
    "wtorek",
    "środa",
    "czwartek",
    "piątek",
    "sobota",
    "niedziela",
]
NO_COLLECTION = {"", "brak", "brak odbioru", "nie dotyczy", "nie wystepuje"}

# How far back weekly rounds are drawn, so the calendar shows recent pickups too.
DAYS_BACK = 28


def fold(text: str) -> str:
    """Lower case, Polish diacritics removed, whitespace collapsed."""
    text = text.replace("ł", "l").replace("Ł", "L")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace("-", " ").split())


def _weekday(word: str) -> int | None:
    if word in WEEKDAYS:
        return WEEKDAYS[word]
    if len(word) < 5:
        return None
    close = difflib.get_close_matches(word, WEEKDAYS, n=1, cutoff=0.8)
    return WEEKDAYS[close[0]] if close else None


@dataclass
class FieldRule:
    """What one ZGK field says."""

    dates: list[date] = field(default_factory=list)
    weekdays: set[int] = field(default_factory=set)
    every_two_weeks: bool = False
    same_as_mixed: bool = False
    note: str | None = None
    raw: str = ""
    suspicious: set[date] = field(default_factory=set)


def parse_field(text: str | None, today: date) -> FieldRule:
    """Read one field of a ZGK record."""
    raw = (text or "").strip()
    rule = FieldRule(raw=raw)
    folded = fold(raw)
    if folded in NO_COLLECTION:
        return rule

    matches = list(DATE_RE.finditer(raw))
    if matches:
        for m in matches:
            day, month, year = (int(g) for g in m.groups())
            if abs(year - today.year) > 1:
                continue  # a typo such as 29.12.2034
            try:
                rule.dates.append(date(year, month, day))
            except ValueError:
                continue  # 31.02. and the like
        tail = raw[matches[-1].end() :].strip(" -–,;")
        rule.note = tail or None
        # A date out of order in an otherwise rising list is likely a typo.
        for prev, cur in zip(rule.dates, rule.dates[1:]):
            if cur < prev:
                rule.suspicious.add(cur)
        return rule

    for word in WORD_RE.findall(folded):
        day = _weekday(word)
        if day is not None:
            rule.weekdays.add(day)
    rule.every_two_weeks = "dwa tygodnie" in folded or "2 tygodnie" in folded
    rule.same_as_mixed = "zgodnie z harmonogramem" in folded
    if not rule.weekdays and not rule.same_as_mixed:
        rule.note = raw  # unknown wording, shown to the user as-is
    return rule


@dataclass(frozen=True)
class Pickup:
    """One collection on one day."""

    waste_type: str
    day: date
    estimated: bool = False  # drawn from a weekday, not a date ZGK published
    holiday: str | None = None
    moved_from: date | None = None
    note: str | None = None
    suspicious: bool = False
    manual: bool = False


@dataclass
class Override:
    """A manual change from the options: move, cancel or add a pickup."""

    waste_type: str | None  # None = every type on that day
    old: date | None  # None = add a new pickup
    new: date | None  # None = cancel


TYPE_ALIASES = {
    "zmieszane": MIXED,
    "zmieszanych": MIXED,
    "mixed": MIXED,
    "selektywne": SELECTIVE,
    "segregowane": SELECTIVE,
    "selective": SELECTIVE,
    "bio": BIO,
    "gabaryty": BULK,
    "wielkogabarytowe": BULK,
    "bulk": BULK,
}
CANCEL_WORDS = {"brak", "nie", "-", "x", "usun", "odwolany", "odwolane"}


class OverrideError(ValueError):
    """A line of the overrides text could not be read."""

    def __init__(self, line_no: int, line: str) -> None:
        super().__init__(f"{line_no}: {line}")
        self.line_no = line_no
        self.line = line


def _date(text: str) -> date:
    m = DATE_RE.fullmatch(text.strip())
    if not m:
        raise ValueError(text)
    day, month, year = (int(g) for g in m.groups())
    return date(year, month, day)


def parse_overrides(text: str | None) -> list[Override]:
    """Read override lines.

    Formats (one per line, '#' starts a comment):
      11.11.2026 > 12.11.2026            move every pickup on that day
      zmieszane 11.11.2026 > 12.11.2026  move one type only
      bio 11.11.2026 > brak              cancel
      + 14.11.2026 bio                   add
    """
    result: list[Override] = []
    for no, line in enumerate((text or "").splitlines(), start=1):
        clean = line.split("#", 1)[0].strip()
        if not clean:
            continue
        try:
            if clean.startswith("+"):
                parts = clean[1:].split()
                new = _date(parts[0])
                types = [TYPE_ALIASES[fold(p)] for p in parts[1:]]
                if not types:
                    raise ValueError(clean)
                result.extend(Override(t, None, new) for t in types)
                continue
            left, right = (p.strip() for p in re.split(r">|->|=>", clean, maxsplit=1))
            words = left.split()
            waste_type = None
            if len(words) == 2:
                waste_type = TYPE_ALIASES[fold(words[0])]
                words = words[1:]
            if len(words) != 1:
                raise ValueError(clean)
            old = _date(words[0])
            new = None if fold(right) in CANCEL_WORDS else _date(right)
            result.append(Override(waste_type, old, new))
        except (ValueError, KeyError, IndexError) as err:
            raise OverrideError(no, line.strip()) from err
    return result


def build_pickups(
    record: dict,
    today: date,
    weeks_ahead: int,
    holiday_mode: str,
    overrides: list[Override] | None = None,
) -> list[Pickup]:
    """All pickups for an address record, sorted by day."""
    rules = {t: parse_field(record.get(t), today) for t in WASTE_TYPES}
    start = today - timedelta(days=DAYS_BACK)
    end = today + timedelta(weeks=weeks_ahead)
    pickups: list[Pickup] = []

    for waste_type, rule in rules.items():
        dates = rule.dates
        estimated = False
        if not dates and rule.same_as_mixed and rules[MIXED].dates:
            dates = rules[MIXED].dates
        elif not dates and rule.weekdays:
            estimated = True
            # A biweekly round has no published anchor date, so it is not drawn.
            if not rule.every_two_weeks:
                dates = [
                    start + timedelta(days=offset)
                    for offset in range((end - start).days + 1)
                    if (start + timedelta(days=offset)).weekday() in rule.weekdays
                ]
        for day in dates:
            pickups.extend(
                _with_holiday(
                    Pickup(
                        waste_type,
                        day,
                        estimated=estimated,
                        note=rule.note if not estimated else None,
                        suspicious=day in rule.suspicious,
                    ),
                    holiday_mode,
                )
            )

    pickups = _apply_overrides(pickups, overrides or [])
    unique = {(p.waste_type, p.day): p for p in pickups}
    return sorted(
        unique.values(), key=lambda p: (p.day, WASTE_TYPES.index(p.waste_type))
    )


def _with_holiday(pickup: Pickup, mode: str) -> list[Pickup]:
    name = holiday_name(pickup.day)
    if not name:
        return [pickup]
    if not pickup.estimated:
        # ZGK published this date itself, keep it and only say it is a holiday.
        return [replace(pickup, holiday=name)]
    if mode == HOLIDAY_SKIP:
        return []
    if mode == HOLIDAY_NEXT_DAY:
        return [
            replace(
                pickup,
                day=next_working_day(pickup.day),
                moved_from=pickup.day,
                holiday=name,
            )
        ]
    return [replace(pickup, holiday=name)]


def _apply_overrides(pickups: list[Pickup], overrides: list[Override]) -> list[Pickup]:
    for ov in overrides:
        if ov.old is None:
            if ov.new is not None and ov.waste_type is not None:
                pickups.append(Pickup(ov.waste_type, ov.new, manual=True))
            continue
        changed: list[Pickup] = []
        for p in pickups:
            hit = p.day == ov.old and ov.waste_type in (None, p.waste_type)
            if not hit:
                changed.append(p)
            elif ov.new is not None:
                changed.append(
                    replace(
                        p, day=ov.new, moved_from=p.moved_from or p.day, manual=True
                    )
                )
        pickups = changed
    return pickups


def describe_rule(text: str | None, today: date) -> str:
    """Short Polish description of how a field is read (for sensor attributes)."""
    rule = parse_field(text, today)
    if rule.dates:
        return "terminy podane przez ZGK"
    if rule.same_as_mixed:
        return "zgodnie z terminami odpadów zmieszanych"
    if rule.weekdays and rule.every_two_weeks:
        return "co dwa tygodnie (ZGK nie podaje dat, pominięto)"
    if rule.weekdays:
        names = [WEEKDAY_NAMES[d] for d in sorted(rule.weekdays)]
        return "co tydzień: " + ", ".join(names)
    if fold(rule.raw) in NO_COLLECTION:
        return "brak odbioru"
    return f"nieznany zapis: {rule.raw}"
