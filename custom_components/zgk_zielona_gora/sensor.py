"""Sensors: next pickup per waste type, next pickup overall, ZGK notices."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import WASTE_ICONS, WASTE_NAMES, WASTE_TYPES
from .coordinator import ZgkConfigEntry, ZgkCoordinator
from .entity import ZgkEntity
from .schedule import Pickup, describe_rule


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZgkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        WasteTypeSensor(coordinator, t) for t in WASTE_TYPES
    ]
    entities += [NextPickupSensor(coordinator), NoticeSensor(coordinator)]
    async_add_entities(entities)


class _DailySensor(ZgkEntity, SensorEntity):
    """Rewrites its state just after midnight so 'days' stays right."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._midnight, hour=0, minute=0, second=10
            )
        )

    @callback
    def _midnight(self, _now: Any) -> None:
        self.async_write_ha_state()

    def _upcoming(self) -> list[Pickup]:
        today = dt_util.now().date()
        return [p for p in self.coordinator.data.pickups if p.day >= today]


def _days(day: date) -> int:
    return (day - dt_util.now().date()).days


class WasteTypeSensor(_DailySensor):
    """Next pickup of one waste type."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: ZgkCoordinator, waste_type: str) -> None:
        super().__init__(coordinator, waste_type)
        self.waste_type = waste_type
        self._attr_translation_key = waste_type
        self._attr_icon = WASTE_ICONS[waste_type]

    def _next(self) -> Pickup | None:
        return next(
            (p for p in self._upcoming() if p.waste_type == self.waste_type), None
        )

    @property
    def native_value(self) -> date | None:
        pickup = self._next()
        return pickup.day if pickup else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pickup = self._next()
        record = self.coordinator.data.record
        upcoming = [
            p.day.isoformat()
            for p in self._upcoming()
            if p.waste_type == self.waste_type
        ][:5]
        return {
            "dni": _days(pickup.day) if pickup else None,
            "wyliczony": pickup.estimated if pickup else None,
            "swieto": pickup.holiday if pickup else None,
            "harmonogram": describe_rule(
                record.get(self.waste_type), dt_util.now().date()
            ),
            "zapis_zgk": record.get(self.waste_type),
            "kolejne": upcoming,
        }


class NextPickupSensor(_DailySensor):
    """The next day with any pickup."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_translation_key = "next_pickup"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: ZgkCoordinator) -> None:
        super().__init__(coordinator, "next_pickup")

    def _next_day(self) -> list[Pickup]:
        upcoming = self._upcoming()
        if not upcoming:
            return []
        first = upcoming[0].day
        return [p for p in upcoming if p.day == first]

    @property
    def native_value(self) -> date | None:
        pickups = self._next_day()
        return pickups[0].day if pickups else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pickups = self._next_day()
        return {
            "dni": _days(pickups[0].day) if pickups else None,
            "rodzaje": [WASTE_NAMES[p.waste_type] for p in pickups],
            "klucze": [p.waste_type for p in pickups],
        }


class NoticeSensor(ZgkEntity, SensorEntity):
    """Latest ZGK notice about schedule changes."""

    _attr_translation_key = "notice"
    _attr_icon = "mdi:bullhorn"

    def __init__(self, coordinator: ZgkCoordinator) -> None:
        super().__init__(coordinator, "notice")

    @property
    def native_value(self) -> str | None:
        news = self.coordinator.data.news
        return news[0].title[:255] if news else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        news = self.coordinator.data.news
        if not news:
            return {}
        return {
            "data": news[0].published.isoformat(),
            "url": news[0].url,
            "poprzednie": [
                {"tytul": n.title, "data": n.published.isoformat(), "url": n.url}
                for n in news[1:5]
            ],
        }
