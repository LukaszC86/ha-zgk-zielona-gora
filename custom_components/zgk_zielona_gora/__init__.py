"""ZGK Zielona Góra waste collection schedule."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import WASTE_TYPES
from .coordinator import ZgkConfigEntry, ZgkCoordinator

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ZgkConfigEntry) -> bool:
    """Set up one address."""
    coordinator = ZgkCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    _remove_unwanted_entities(hass, entry, coordinator.waste_types)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZgkConfigEntry) -> bool:
    """Unload an address."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _options_updated(hass: HomeAssistant, entry: ZgkConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _remove_unwanted_entities(
    hass: HomeAssistant, entry: ZgkConfigEntry, wanted: list[str]
) -> None:
    """Drop the calendar and sensor of every waste type the user turned off."""
    dropped = [t for t in WASTE_TYPES if t not in wanted]
    keys = {f"{entry.entry_id}_{t}" for t in dropped}
    keys |= {f"{entry.entry_id}_calendar_{t}" for t in dropped}
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id in keys:
            registry.async_remove(entity.entity_id)
        elif entity.domain == "calendar" and entity.device_id is not None:
            # Up to 0.2.1 calendars were attached to the address device.
            registry.async_update_entity(entity.entity_id, device_id=None)
