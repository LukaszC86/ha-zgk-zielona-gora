"""Config and options flows."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .api import ZgkClient, ZgkError
from .const import (
    CONF_ADDRESS,
    CONF_HOLIDAY_MODE,
    CONF_OVERRIDES,
    CONF_SEARCH,
    CONF_TITLE,
    CONF_WASTE_TYPES,
    CONF_WEEKS_AHEAD,
    DEFAULT_HOLIDAY_MODE,
    DEFAULT_WEEKS_AHEAD,
    DOMAIN,
    HOLIDAY_MODES,
    MAX_SUGGESTIONS,
    WASTE_TYPES,
)
from .coordinator import ZgkConfigEntry
from .schedule import OverrideError, fold, parse_overrides


class ZgkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Find an address in the ZGK search and add it."""

    VERSION = 1

    def __init__(self) -> None:
        self._suggestions: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            term = user_input[CONF_SEARCH].strip()
            client = ZgkClient(async_get_clientsession(self.hass))
            try:
                found = await client.search(term)
            except ZgkError:
                errors["base"] = "cannot_connect"
            else:
                exact = [s for s in found if fold(str(s["value"])) == fold(term)]
                if len(exact) == 1:
                    return await self._create(exact[0])
                if not found:
                    errors[CONF_SEARCH] = "not_found"
                elif len(found) > MAX_SUGGESTIONS:
                    errors[CONF_SEARCH] = "too_many"
                else:
                    self._suggestions = found
                    return await self.async_step_pick()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_SEARCH): TextSelector()}),
            errors=errors,
        )

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            chosen = next(
                s for s in self._suggestions if s["value"] == user_input[CONF_ADDRESS]
            )
            return await self._create(chosen)
        options = [
            SelectOptionDict(
                value=str(s["value"]),
                label=" ".join(str(s.get("title") or s["value"]).split()),
            )
            for s in self._suggestions
        ]
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            description_placeholders={"count": str(len(options))},
        )

    async def _create(self, record: dict) -> ConfigFlowResult:
        address = str(record["value"]).strip()
        await self.async_set_unique_id(fold(address))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=address,
            data={CONF_ADDRESS: address, CONF_TITLE: record.get("title") or address},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ZgkConfigEntry) -> OptionsFlow:
        return ZgkOptionsFlow()


class ZgkOptionsFlow(OptionsFlow):
    """Weeks ahead, holiday handling and manual changes."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"line": ""}
        if user_input is not None and not user_input.get(CONF_WASTE_TYPES):
            errors[CONF_WASTE_TYPES] = "no_waste_types"
        elif user_input is not None:
            try:
                parse_overrides(user_input.get(CONF_OVERRIDES))
            except OverrideError as err:
                errors[CONF_OVERRIDES] = "bad_override"
                placeholders["line"] = f"{err.line_no}: {err.line}"
            else:
                user_input[CONF_WEEKS_AHEAD] = int(user_input[CONF_WEEKS_AHEAD])
                return self.async_create_entry(data=user_input)
        current = user_input or self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_WASTE_TYPES,
                    default=list(current.get(CONF_WASTE_TYPES) or WASTE_TYPES),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(WASTE_TYPES),
                        translation_key="waste_type",
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(
                    CONF_WEEKS_AHEAD,
                    default=current.get(CONF_WEEKS_AHEAD, DEFAULT_WEEKS_AHEAD),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=2, max=104, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_HOLIDAY_MODE,
                    default=current.get(CONF_HOLIDAY_MODE, DEFAULT_HOLIDAY_MODE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=HOLIDAY_MODES,
                        translation_key="holiday_mode",
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    CONF_OVERRIDES,
                    description={"suggested_value": current.get(CONF_OVERRIDES, "")},
                ): TextSelector(TextSelectorConfig(multiline=True)),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )
