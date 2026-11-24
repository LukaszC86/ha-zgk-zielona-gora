from freezegun import freeze_time
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zgk_zielona_gora.const import DOMAIN, NEWS_URL, SEARCH_URL


def _state(hass, key):
    reg = er.async_get(hass)
    for ent in reg.entities.values():
        if ent.unique_id.endswith("_" + key):
            return hass.states.get(ent.entity_id)
    raise AssertionError(key)


def _mock(aioclient_mock, records, news_html, match):
    aioclient_mock.get(
        SEARCH_URL,
        json={
            "result": 1,
            "message": "",
            "suggests": [r for r in records.values() if match(r)],
        },
    )
    aioclient_mock.get(NEWS_URL, text=news_html)


@freeze_time("2026-11-24 09:00:00+01:00")
async def test_flow_exact_match_and_entities(
    hass: HomeAssistant, aioclient_mock, records, news_html
):
    _mock(aioclient_mock, records, news_html, lambda r: r["value"] == "AKADEMICKA 1")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search": "akademicka 1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AKADEMICKA 1"
    await hass.async_block_till_done()

    mixed = _state(hass, "mixed")
    assert mixed.state == "2026-11-25"
    assert mixed.attributes["dni"] == 1
    assert mixed.attributes["wyliczony"] is True
    nxt = _state(hass, "next_pickup")
    assert nxt.state == "2026-11-25"
    assert set(nxt.attributes["klucze"]) == {"mixed", "bio"}
    notice = _state(hass, "notice")
    assert notice.state.startswith("11 listopada")
    # one calendar per waste type, the combined one is disabled by default
    reg = er.async_get(hass)
    combined = next(
        e for e in reg.entities.values() if e.unique_id.endswith("_calendar")
    )
    assert combined.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    cal = _state(hass, "calendar_mixed")
    assert cal.attributes["message"] == "Odpady zmieszane"
    assert _state(hass, "calendar_bio").attributes["message"] == "Odpady BIO"

    async def events(key, start, end):
        entity_id = _state(hass, key).entity_id
        resp = await hass.services.async_call(
            "calendar",
            "get_events",
            {"entity_id": entity_id, "start_date_time": start, "end_date_time": end},
            blocking=True,
            return_response=True,
        )
        return {(e["start"], e["summary"]) for e in resp[entity_id]["events"]}

    december = ("2026-12-01 00:00:00", "2026-12-31 23:59:59")
    selective = await events("calendar_selective", *december)
    assert ("2026-12-15", "Odpady selektywne") in selective
    assert {s for _, s in selective} == {"Odpady selektywne"}
    mixed = await events("calendar_mixed", *december)
    assert ("2026-12-23", "Odpady zmieszane") in mixed
    assert {s for _, s in mixed} == {"Odpady zmieszane"}
    assert ("2026-12-02", "Odpady BIO") in await events("calendar_bio", *december)


async def test_flow_pick_from_list(
    hass: HomeAssistant, aioclient_mock, records, news_html
):
    _mock(aioclient_mock, records, news_html, lambda r: True)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search": "a"}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "pick"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": "BOTANICZNA 1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["address"] == "BOTANICZNA 1"


async def test_flow_not_found(hass: HomeAssistant, aioclient_mock, records, news_html):
    _mock(aioclient_mock, records, news_html, lambda r: False)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search": "nieistniejaca"}
    )
    assert result["errors"] == {"search": "not_found"}


@freeze_time("2026-11-24 09:00:00+01:00")
async def test_options_flow(hass: HomeAssistant, aioclient_mock, records, news_html):
    _mock(aioclient_mock, records, news_html, lambda r: r["value"] == "AKADEMICKA 1")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "AKADEMICKA 1", "title": "AKADEMICKA 1"},
        unique_id="akademicka 1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"waste_types": [], "weeks_ahead": 10, "holiday_mode": "skip"},
    )
    assert result["errors"] == {"waste_types": "no_waste_types"}
    no_bio = ["mixed", "selective", "bulk"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "waste_types": no_bio,
            "weeks_ahead": 10,
            "holiday_mode": "skip",
            "overrides": "zle",
        },
    )
    assert result["errors"] == {"overrides": "bad_override"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "waste_types": no_bio,
            "weeks_ahead": 10,
            "holiday_mode": "skip",
            "overrides": "zmieszane 25.11.2026 > 26.11.2026",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    mixed = _state(hass, "mixed")
    assert mixed.state == "2026-11-26"

    # BIO turned off: its calendar and sensor are gone, next pickup ignores it
    reg = er.async_get(hass)
    uids = {
        e.unique_id.removeprefix(entry.entry_id + "_") for e in reg.entities.values()
    }
    assert "bio" not in uids and "calendar_bio" not in uids
    assert {"mixed", "calendar_mixed", "calendar_selective"} <= uids
    nxt = _state(hass, "next_pickup")
    assert nxt.state == "2026-11-26"
    assert nxt.attributes["klucze"] == ["mixed"]


@freeze_time("2026-11-24 09:00:00+01:00")
async def test_calendar_names_without_address(
    hass: HomeAssistant, aioclient_mock, records, news_html
):
    _mock(aioclient_mock, records, news_html, lambda r: r["value"] == "AKADEMICKA 1")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "AKADEMICKA 1", "title": "AKADEMICKA 1"},
        unique_id="akademicka 1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    bio = _state(hass, "calendar_bio")
    assert bio.entity_id == "calendar.odpady_bio"
    assert bio.attributes["friendly_name"] == "Odpady BIO"
    assert _state(hass, "calendar_bulk").attributes["friendly_name"] == "Gabaryty"
    # calendars have no device, so the UI cannot prefix the address
    reg = er.async_get(hass)
    cal_entry = reg.async_get(bio.entity_id)
    assert cal_entry.device_id is None
    assert cal_entry.config_entry_id == entry.entry_id
    assert reg.async_get(_state(hass, "bio").entity_id).device_id is not None
    # sensors keep the address prefix
    assert "akademicka_1" in _state(hass, "bio").entity_id


async def test_old_calendar_detached_from_device(
    hass: HomeAssistant, aioclient_mock, records, news_html
):
    _mock(aioclient_mock, records, news_html, lambda r: r["value"] == "AKADEMICKA 1")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "AKADEMICKA 1", "title": "AKADEMICKA 1"},
        unique_id="akademicka 1",
    )
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, entry.entry_id)}
    )
    reg = er.async_get(hass)
    old = reg.async_get_or_create(
        "calendar",
        DOMAIN,
        f"{entry.entry_id}_calendar_bio",
        config_entry=entry,
        device_id=device.id,
        suggested_object_id="zgk_racula_odpady_bio",
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    updated = reg.async_get(old.entity_id)
    assert updated.entity_id == old.entity_id
    assert updated.device_id is None
