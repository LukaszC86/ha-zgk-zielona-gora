
from freezegun import freeze_time
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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
    cal = _state(hass, "calendar")
    assert cal.attributes["message"] == "Odpady zmieszane"

    events = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": cal.entity_id,
            "start_date_time": "2026-12-01 00:00:00",
            "end_date_time": "2026-12-31 23:59:59",
        },
        blocking=True,
        return_response=True,
    )
    items = events[cal.entity_id]["events"]
    summaries = {(e["start"], e["summary"]) for e in items}
    assert ("2026-12-15", "Odpady selektywne") in summaries
    assert ("2026-12-02", "Odpady BIO") in summaries
    # 23.12 is a Wednesday, not a holiday; nothing drawn falls on 24-26.12 here
    assert ("2026-12-23", "Odpady zmieszane") in summaries


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
        {"weeks_ahead": 10, "holiday_mode": "skip", "overrides": "zle"},
    )
    assert result["errors"] == {"overrides": "bad_override"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "weeks_ahead": 10,
            "holiday_mode": "skip",
            "overrides": "zmieszane 25.11.2026 > 26.11.2026",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    mixed = _state(hass, "mixed")
    assert mixed.state == "2026-11-26"
