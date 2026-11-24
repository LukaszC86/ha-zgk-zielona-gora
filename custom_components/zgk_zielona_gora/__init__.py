"""ZGK Zielona Góra waste collection schedule."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ZgkConfigEntry, ZgkCoordinator

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ZgkConfigEntry) -> bool:
    """Set up one address."""
    coordinator = ZgkCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZgkConfigEntry) -> bool:
    """Unload an address."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _options_updated(hass: HomeAssistant, entry: ZgkConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
