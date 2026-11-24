"""Data update coordinator for ZGK Zielona Góra."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NewsItem, ZgkClient, ZgkError
from .const import (
    CONF_ADDRESS,
    CONF_HOLIDAY_MODE,
    CONF_OVERRIDES,
    CONF_WEEKS_AHEAD,
    DEFAULT_HOLIDAY_MODE,
    DEFAULT_WEEKS_AHEAD,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .schedule import OverrideError, Pickup, build_pickups, parse_overrides

_LOGGER = logging.getLogger(__name__)

type ZgkConfigEntry = ConfigEntry[ZgkCoordinator]


@dataclass
class ZgkData:
    """What the entities read."""

    record: dict
    pickups: list[Pickup]
    news: list[NewsItem] = field(default_factory=list)


class ZgkCoordinator(DataUpdateCoordinator[ZgkData]):
    """Fetches the address record and builds the pickups."""

    config_entry: ZgkConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ZgkConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = ZgkClient(async_get_clientsession(hass))
        self._record: dict | None = None

    @property
    def address(self) -> str:
        return self.config_entry.data[CONF_ADDRESS]

    async def _async_update_data(self) -> ZgkData:
        try:
            record = await self.client.address(self.address)
        except ZgkError as err:
            if self._record is None:
                raise UpdateFailed(f"ZGK niedostępne: {err}") from err
            _LOGGER.warning("ZGK unreachable, keeping the last schedule: %s", err)
            record = self._record
        if record is None:
            raise UpdateFailed(f"ZGK nie zna już adresu {self.address!r}")
        self._record = record

        news: list[NewsItem] = self.data.news if self.data else []
        try:
            news = await self.client.schedule_news()
        except ZgkError as err:
            _LOGGER.debug("ZGK news unavailable: %s", err)

        return ZgkData(record, self.rebuild(record), news)

    def rebuild(self, record: dict) -> list[Pickup]:
        """Pickups from a record with the current options."""
        options = self.config_entry.options
        try:
            overrides = parse_overrides(options.get(CONF_OVERRIDES))
        except OverrideError as err:
            _LOGGER.error("Ignoring overrides, bad line %s", err)
            overrides = []
        return build_pickups(
            record,
            dt_util.now().date(),
            int(options.get(CONF_WEEKS_AHEAD, DEFAULT_WEEKS_AHEAD)),
            options.get(CONF_HOLIDAY_MODE, DEFAULT_HOLIDAY_MODE),
            overrides,
        )
