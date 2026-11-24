from datetime import date

import pytest

from custom_components.zgk_zielona_gora.api import parse_news
from custom_components.zgk_zielona_gora.holidays_pl import easter_sunday, holiday_name
from custom_components.zgk_zielona_gora.schedule import (
    OverrideError,
    build_pickups,
    describe_rule,
    parse_field,
    parse_overrides,
)

TODAY = date(2026, 11, 24)  # a Tuesday


def by_type(pickups, waste_type):
    return [p for p in pickups if p.waste_type == waste_type]


def test_weekly_mixed_and_bio_are_drawn(records):
    pickups = build_pickups(records["AKADEMICKA 1"], TODAY, 8, "mark")
    mixed = by_type(pickups, "mixed")
    assert all(p.day.weekday() == 2 for p in mixed)
    assert all(p.estimated for p in mixed)
    assert date(2026, 11, 25) in [p.day for p in mixed]
    assert len(by_type(pickups, "bio")) == len(mixed)
    # explicit dates are all kept, past ones included
    selective = by_type(pickups, "selective")
    assert len(selective) == 26 and not any(p.estimated for p in selective)
    assert [p.day for p in by_type(pickups, "bulk")] == [
        date(2026, 2, 23),
        date(2026, 8, 3),
    ]
    assert by_type(pickups, "bulk")[0].note.startswith("podane daty")


def test_typo_date_is_flagged(records):
    pickups = build_pickups(records["AKADEMICKA 1"], TODAY, 8, "mark")
    flagged = [p.day for p in pickups if p.suspicious]
    assert flagged == [date(2026, 11, 1)]


def test_two_weekdays(records):
    pickups = build_pickups(records["BOTANICZNA 1"], TODAY, 4, "mark")
    assert {p.day.weekday() for p in by_type(pickups, "mixed")} == {0, 4}


def test_bio_same_as_mixed_dates(records):
    pickups = build_pickups(records["ZATONIE-Chabrowa 1"], TODAY, 4, "mark")
    assert [p.day for p in by_type(pickups, "bio")] == [
        p.day for p in by_type(pickups, "mixed")
    ]
    assert not any(p.estimated for p in by_type(pickups, "bio"))


def test_brak_and_capitalised_weekday(records):
    pickups = build_pickups(records["OCHLA -BAKALIOWA"], TODAY, 4, "mark")
    assert by_type(pickups, "mixed") == [] and by_type(pickups, "bulk") == []
    assert {p.day.weekday() for p in by_type(pickups, "bio")} == {3}
    pickups = build_pickups(records["RACULA- BAJECZNA 1/1"], TODAY, 4, "mark")
    assert {p.day.weekday() for p in by_type(pickups, "bio")} == {4}


@pytest.mark.parametrize(
    "text,day", [("czawartek", 3), ("CZWARTEK", 3), ("Piątek", 4), ("sroda", 2)]
)
def test_weekday_spellings(text, day):
    assert parse_field(text, TODAY).weekdays == {day}


def test_implausible_year_dropped():
    rule = parse_field("12.12.2026, 29.12.2034", TODAY)
    assert rule.dates == [date(2026, 12, 12)]


def test_unknown_text_kept_as_note():
    rule = parse_field("na zgłoszenie", TODAY)
    assert not rule.dates and not rule.weekdays and rule.note == "na zgłoszenie"


def test_holidays():
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert holiday_name(date(2026, 6, 4)) == "Boże Ciało"
    assert holiday_name(date(2026, 12, 24)) == "Wigilia"
    assert holiday_name(date(2026, 12, 23)) is None


def test_holiday_modes(records):
    rec = {"mixed": "czwartek"}  # 24.12.2026 is a Thursday holiday
    today = date(2026, 12, 1)
    marked = build_pickups(rec, today, 6, "mark")
    hit = [p for p in marked if p.day == date(2026, 12, 24)]
    assert hit and hit[0].holiday == "Wigilia"
    skipped = build_pickups(rec, today, 6, "skip")
    assert date(2026, 12, 24) not in [p.day for p in skipped]
    moved = build_pickups(rec, today, 6, "next_day")
    # 25 and 26 are holidays, 27 is a Sunday
    assert any(
        p.day == date(2026, 12, 28) and p.moved_from == date(2026, 12, 24)
        for p in moved
    )


def test_explicit_dates_not_moved_on_holiday():
    rec = {"selective": "24.12.2026"}
    pickups = build_pickups(rec, date(2026, 12, 1), 6, "next_day")
    assert [p.day for p in pickups] == [date(2026, 12, 24)]
    assert pickups[0].holiday == "Wigilia"


def test_overrides(records):
    text = """
    # przesunięcie po 11 listopada
    zmieszane 25.11.2026 > 26.11.2026
    bio 25.11.2026 > brak
    selektywne 01.11.2026 > 01.12.2026
    + 28.11.2026 gabaryty
    """
    pickups = build_pickups(
        records["AKADEMICKA 1"], TODAY, 4, "mark", parse_overrides(text)
    )
    days = {(p.waste_type, p.day) for p in pickups}
    assert ("mixed", date(2026, 11, 26)) in days
    assert ("mixed", date(2026, 11, 25)) not in days
    assert ("bio", date(2026, 11, 25)) not in days
    assert ("selective", date(2026, 12, 1)) in days
    assert ("bulk", date(2026, 11, 28)) in days


def test_override_all_types():
    pickups = build_pickups(
        {"mixed": "środa", "bio": "środa"},
        TODAY,
        2,
        "mark",
        parse_overrides("25.11.2026 > 27.11.2026"),
    )
    assert {p.waste_type for p in pickups if p.day == date(2026, 11, 27)} == {
        "mixed",
        "bio",
    }


@pytest.mark.parametrize(
    "line", ["25.11.2026", "foo 25.11.2026 > brak", "+ 25.11.2026", "31.02.2026 > brak"]
)
def test_bad_override(line):
    with pytest.raises(OverrideError):
        parse_overrides(line)


def test_describe(records):
    rec = records["ZATONIE-Chabrowa 1"]
    assert describe_rule(rec["bio"], TODAY) == "zgodnie z terminami odpadów zmieszanych"
    assert (
        describe_rule("poniedziałek, piątek", TODAY)
        == "co tydzień: poniedziałek, piątek"
    )
    assert describe_rule("BRAK", TODAY) == "brak odbioru"


def test_news(news_html):
    news = parse_news(news_html)
    assert [n.published for n in news] == [date(2026, 11, 5), date(2026, 5, 28)]
    assert news[0].url.endswith("-i166")
