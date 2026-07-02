from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from scrapers.arbeitnow import ArbeitnowScraper

FIXTURE = Path(__file__).parent / "fixtures" / "arbeitnow_jobs.json"


@patch("scrapers.arbeitnow.requests.get")
def test_arbeitnow_filters_by_title_keyword(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mock_get.return_value = resp

    results = ArbeitnowScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Acme Remote"
    assert results[0].source == "Arbeitnow"


@patch("scrapers.arbeitnow.requests.get")
def test_arbeitnow_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 500
    mock_get.return_value = resp
    assert ArbeitnowScraper().search(["python"]) == []
