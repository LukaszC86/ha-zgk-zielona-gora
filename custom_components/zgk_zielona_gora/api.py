"""HTTP client for www.zgk.net.pl."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date

import aiohttp

from .const import BASE_URL, NEWS_URL, REQUEST_HEADERS, SEARCH_URL

TIMEOUT = aiohttp.ClientTimeout(total=30)

NEWS_ITEM_RE = re.compile(
    r'<a href="(?P<href>/aktualnosci/[^"]+)"[^>]*>(?:(?!</a>).)*?'
    r'<time datetime="(?P<date>\d{4}-\d{2}-\d{2})">(?:(?!</a>).)*?'
    r'<div class="h1">(?P<title>.*?)</div>',
    re.DOTALL,
)
SCHEDULE_NEWS_RE = re.compile(r"harmonogram|odbi[oó]r\w* odpad", re.IGNORECASE)


class ZgkError(Exception):
    """ZGK could not be reached or answered with something unexpected."""


@dataclass(frozen=True)
class NewsItem:
    """One ZGK news item about schedule changes."""

    title: str
    published: date
    url: str


class ZgkClient:
    """Talks to the ZGK website."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def search(self, term: str) -> list[dict]:
        """Address suggestions, each with its schedule fields."""
        try:
            async with self._session.get(
                SEARCH_URL,
                params={"term": term},
                headers=REQUEST_HEADERS,
                timeout=TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise ZgkError(str(err)) from err
        if not isinstance(data, dict) or data.get("result") != 1:
            raise ZgkError(f"unexpected answer: {str(data)[:200]}")
        suggests = data.get("suggests") or []
        return [s for s in suggests if isinstance(s, dict) and s.get("value")]

    async def address(self, address: str) -> dict | None:
        """The record whose value equals the address (folded), or None."""
        from .schedule import fold

        wanted = fold(address)
        for record in await self.search(address):
            if fold(str(record["value"])) == wanted:
                return record
        return None

    async def schedule_news(self) -> list[NewsItem]:
        """News items about schedule changes, newest first."""
        try:
            async with self._session.get(
                NEWS_URL,
                headers={"User-Agent": REQUEST_HEADERS["User-Agent"]},
                timeout=TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ZgkError(str(err)) from err
        return parse_news(text)


def parse_news(page: str) -> list[NewsItem]:
    """Schedule-change news from the /aktualnosci HTML."""
    items = []
    for m in NEWS_ITEM_RE.finditer(page):
        title = html.unescape(re.sub(r"<[^>]+>", "", m["title"])).strip()
        if not SCHEDULE_NEWS_RE.search(title):
            continue
        items.append(
            NewsItem(title, date.fromisoformat(m["date"]), BASE_URL + m["href"])
        )
    items.sort(key=lambda n: n.published, reverse=True)
    return items
