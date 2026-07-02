from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.yenibiris import YenibirisScraper

FIXTURE = Path(__file__).parent / "fixtures" / "yenibiris_search.html"


def _mock_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.content = FIXTURE.read_bytes()
    return resp


@patch("scrapers.yenibiris.requests.get")
def test_yenibiris_extracts_title_link_and_matching_company(mock_get):
    mock_get.return_value = _mock_response()
    results = YenibirisScraper().search(["yazılım"], limit=10)
    assert len(results) == 1
    r = results[0]
    assert r.title == "Yazılım Geliştirici"
    assert r.company == "Frigo Soğutma San Tic A.Ş"
    assert r.url == "https://www.yenibiris.com/is-ilani/yazilim-gelistirici/1210713"
    assert r.source == "Yenibiris"


@patch("scrapers.yenibiris.requests.get")
def test_yenibiris_matches_second_listing_by_different_keyword(mock_get):
    mock_get.return_value = _mock_response()
    results = YenibirisScraper().search(["backend"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Wanda Vista İstanbul"


@patch("scrapers.yenibiris.requests.get")
def test_yenibiris_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 403
    mock_get.return_value = resp
    assert YenibirisScraper().search(["python"]) == []
