"""Calendar with every pickup for an address."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import WASTE_NAMES
from .coordinator import ZgkConfigEntry, ZgkCoordinator
from .entity import ZgkEntity
from .schedule import WEEKDAY_NAMES, Pickup


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZgkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the calendar."""
    async_add_entities([ZgkCalendar(entry.runtime_data)])


def pickup_event(pickup: Pickup, news_url: str | None) -> CalendarEvent:
    """Calendar event for a pickup."""
    summary = WASTE_NAMES[pickup.waste_type]
    lines: list[str] = []
    if pickup.estimated:
        weekday = WEEKDAY_NAMES[(pickup.moved_from or pickup.day).weekday()]
        lines.append(f"Termin wyliczony z harmonogramu tygodniowego ZGK ({weekday}).")
    if pickup.holiday:
        if pickup.moved_from and not pickup.manual:
            lines.append(
                f"Przesunięty z {pickup.moved_from:%d.%m.%Y} ({pickup.holiday})."
            )
        else:
            lines.append(f"Dzień wolny: {pickup.holiday}.")
        if pickup.estimated:
            summary = f"⚠ {summary} (święto)"
            lines.append(
                "ZGK może zmienić termin, sprawdź komunikat"
                + (f": {news_url}" if news_url else " na www.zgk.net.pl/aktualnosci.")
            )
    if pickup.manual:
        lines.append(
            f"Zmiana ręczna (z {pickup.moved_from:%d.%m.%Y})."
            if pickup.moved_from
            else "Dodany ręcznie."
        )
    if pickup.suspicious:
        lines.append(
            "⚠ Data poza kolejnością na liście ZGK, możliwa pomyłka po stronie ZGK."
        )
    if pickup.note:
        lines.append(pickup.note)
    return CalendarEvent(
        start=pickup.day,
        end=pickup.day + timedelta(days=1),
        summary=summary,
        description="\n".join(lines) or None,
        uid=f"{pickup.waste_type}-{pickup.day.isoformat()}",
    )


class ZgkCalendar(ZgkEntity, CalendarEntity):
    """All pickups for one address."""

    _attr_translation_key = "schedule"
    _attr_icon = "mdi:delete-empty"

    def __init__(self, coordinator: ZgkCoordinator) -> None:
        super().__init__(coordinator, "calendar")

    def _news_url(self) -> str | None:
        news = self.coordinator.data.news
        return news[0].url if news else None

    @property
    def event(self) -> CalendarEvent | None:
        today = dt_util.now().date()
        for pickup in self.coordinator.data.pickups:
            if pickup.day >= today:
                return pickup_event(pickup, self._news_url())
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start: date = dt_util.as_local(start_date).date()
        end: date = dt_util.as_local(end_date).date()
        url = self._news_url()
        return [
            pickup_event(p, url)
            for p in self.coordinator.data.pickups
            if start <= p.day <= end
        ]
