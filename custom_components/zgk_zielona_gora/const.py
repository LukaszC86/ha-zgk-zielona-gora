"""Constants for the ZGK Zielona Góra integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "zgk_zielona_gora"

BASE_URL: Final = "https://www.zgk.net.pl"
SEARCH_URL: Final = f"{BASE_URL}/ajax-request/search/collection/"
NEWS_URL: Final = f"{BASE_URL}/aktualnosci"
SCHEDULE_PAGE_URL: Final = f"{BASE_URL}/odbior-odpadow"

# Without these headers the search endpoint answers with the HTML page.
REQUEST_HEADERS: Final = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "HomeAssistant-ZGK-Zielona-Gora",
}

UPDATE_INTERVAL: Final = timedelta(hours=6)

CONF_ADDRESS: Final = "address"
CONF_TITLE: Final = "title"
CONF_WEEKS_AHEAD: Final = "weeks_ahead"
CONF_HOLIDAY_MODE: Final = "holiday_mode"
CONF_OVERRIDES: Final = "overrides"
CONF_SEARCH: Final = "search"

DEFAULT_WEEKS_AHEAD: Final = 26

HOLIDAY_MARK: Final = "mark"
HOLIDAY_SKIP: Final = "skip"
HOLIDAY_NEXT_DAY: Final = "next_day"
HOLIDAY_MODES: Final = [HOLIDAY_MARK, HOLIDAY_NEXT_DAY, HOLIDAY_SKIP]
DEFAULT_HOLIDAY_MODE: Final = HOLIDAY_MARK

# Waste type keys as ZGK names the JSON fields.
MIXED: Final = "mixed"
SELECTIVE: Final = "selective"
BIO: Final = "bio"
BULK: Final = "bulk"
WASTE_TYPES: Final = (MIXED, SELECTIVE, BIO, BULK)

WASTE_NAMES: Final = {
    MIXED: "Odpady zmieszane",
    SELECTIVE: "Odpady selektywne",
    BIO: "Odpady BIO",
    BULK: "Gabaryty",
}

WASTE_ICONS: Final = {
    MIXED: "mdi:trash-can",
    SELECTIVE: "mdi:recycle",
    BIO: "mdi:leaf",
    BULK: "mdi:sofa",
}

# More than this many suggestions and the address picker asks for a narrower search.
MAX_SUGGESTIONS: Final = 300
