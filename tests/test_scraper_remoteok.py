import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import requests

from scrapers.remoteok import RemoteOkScraper

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok_jobs.json"


def _mock_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return resp


@patch("scrapers.remoteok.requests.get")
def test_remoteok_skips_legal_notice_entry(mock_get):
    mock_get.return_value = _mock_response()
    results = RemoteOkScraper().search(["python"], limit=10)
    assert all(r.title for r in results)


@patch("scrapers.remoteok.requests.get")
def test_remoteok_filters_by_keyword_in_title_or_tags(mock_get):
    mock_get.return_value = _mock_response()
    results = RemoteOkScraper().search(["react"], limit=10)
    assert len(results) == 1
    assert results[0].title == "React Engineer"
    assert results[0].company == "Beta Inc"
    assert results[0].url == "https://remoteOK.com/remote-jobs/remote-react-engineer-beta-1134361"
    assert results[0].source == "RemoteOK"


@patch("scrapers.remoteok.requests.get")
def test_remoteok_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 500
    mock_get.return_value = resp
    assert RemoteOkScraper().search(["python"]) == []


@patch("scrapers.remoteok.requests.get")
def test_remoteok_returns_empty_list_on_exception(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("boom")
    assert RemoteOkScraper().search(["python"]) == []
