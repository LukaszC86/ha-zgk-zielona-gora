"""Calendar with every pickup for an address."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import WASTE_ICONS, WASTE_NAMES
from .coordinator import ZgkConfigEntry, ZgkCoordinator
from .entity import ZgkEntity
from .schedule import WEEKDAY_NAMES, Pickup


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZgkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One calendar per chosen waste type, plus a combined one (off by default)."""
    coordinator = entry.runtime_data
    entities: list[ZgkCalendar] = [
        ZgkCalendar(coordinator, t) for t in coordinator.waste_types
    ]
    entities.append(ZgkCalendar(coordinator))
    async_add_entities(entities)


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
    """Pickups of one waste type, or of all chosen types when waste_type is None.

    Home Assistant shows each calendar entity in its own colour and lets the
    user tick which ones the calendar panel and cards display.

    The calendar panel lists calendars by friendly name, so the name is just the
    waste type ("Odpady BIO"), without the device (address) prefix.
    """

    _attr_has_entity_name = False
    # Since 2026.11 the frontend puts the device name in front of an entity's
    # name wherever context is needed, so the calendars are not attached to the
    # address device; they still belong to the config entry.
    _attr_device_info = None

    def __init__(
        self, coordinator: ZgkCoordinator, waste_type: str | None = None
    ) -> None:
        if waste_type is None:
            super().__init__(coordinator, "calendar")
            self._attr_name = "Wszystkie odbiory"
            self._attr_icon = "mdi:delete-empty"
            self._attr_entity_registry_enabled_default = False
        else:
            super().__init__(coordinator, f"calendar_{waste_type}")
            self._attr_name = WASTE_NAMES[waste_type]
            self._attr_icon = WASTE_ICONS[waste_type]
        self._attr_device_info = None
        self.waste_type = waste_type

    def _pickups(self) -> list[Pickup]:
        return [
            p
            for p in self.coordinator.data.pickups
            if self.waste_type in (None, p.waste_type)
        ]

    def _news_url(self) -> str | None:
        news = self.coordinator.data.news
        return news[0].url if news else None

    @property
    def event(self) -> CalendarEvent | None:
        today = dt_util.now().date()
        for pickup in self._pickups():
            if pickup.day >= today:
                return pickup_event(pickup, self._news_url())
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start: date = dt_util.as_local(start_date).date()
        end: date = dt_util.as_local(end_date).date()
        url = self._news_url()
        return [pickup_event(p, url) for p in self._pickups() if start <= p.day <= end]
