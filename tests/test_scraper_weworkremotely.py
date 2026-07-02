from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.weworkremotely import WeWorkRemotelyScraper

FIXTURE = Path(__file__).parent / "fixtures" / "weworkremotely.xml"


def _mock_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.content = FIXTURE.read_bytes()
    return resp


@patch("scrapers.weworkremotely.requests.get")
def test_wwr_parses_title_company_from_colon_format(mock_get):
    mock_get.return_value = _mock_response()
    results = WeWorkRemotelyScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Acme Corp"
    assert results[0].title == "Senior Python Developer"
    assert results[0].url == "https://weworkremotely.com/remote-jobs/acme-corp-senior-python-developer"
    assert results[0].source == "WeWorkRemotely"


@patch("scrapers.weworkremotely.requests.get")
def test_wwr_matches_react_keyword(mock_get):
    mock_get.return_value = _mock_response()
    results = WeWorkRemotelyScraper().search(["react"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Beta Inc"


@patch("scrapers.weworkremotely.requests.get")
def test_wwr_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 404
    mock_get.return_value = resp
    assert WeWorkRemotelyScraper().search(["python"]) == []
