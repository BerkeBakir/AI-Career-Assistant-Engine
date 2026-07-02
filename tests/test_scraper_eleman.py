from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.eleman import ElemanScraper

FIXTURE = Path(__file__).parent / "fixtures" / "eleman_search.html"


def _mock_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.content = FIXTURE.read_bytes()
    return resp


@patch("scrapers.eleman.requests.get")
def test_eleman_extracts_title_stripped_of_phone_icon_span(mock_get):
    mock_get.return_value = _mock_response()
    results = ElemanScraper().search(["yazılım"], limit=10)
    assert len(results) == 1
    r = results[0]
    assert r.title == "Yazılım Geliştirici"
    assert r.url == "https://www.eleman.net/is-ilani/yazilim-gelistirici-i4702359"
    assert r.source == "Eleman.net"


@patch("scrapers.eleman.requests.get")
def test_eleman_splits_company_and_location_from_subtitle(mock_get):
    mock_get.return_value = _mock_response()
    results = ElemanScraper().search(["yazılım"], limit=10)
    r = results[0]
    assert r.company == "Acme Yazılım A.Ş."
    assert r.location == "İstanbul Anadolu - Kartal"


@patch("scrapers.eleman.requests.get")
def test_eleman_matches_second_listing_by_keyword(mock_get):
    mock_get.return_value = _mock_response()
    results = ElemanScraper().search(["frontend"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Beta Teknoloji Ltd."
    assert results[0].location == "Ankara - Çankaya"


@patch("scrapers.eleman.requests.get")
def test_eleman_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 500
    mock_get.return_value = resp
    assert ElemanScraper().search(["python"]) == []
