import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def records() -> dict[str, dict]:
    data = json.loads((FIXTURES / "records.json").read_text(encoding="utf-8"))
    return {r["value"]: r for r in data}


@pytest.fixture
def news_html() -> str:
    return (FIXTURES / "news.html").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
