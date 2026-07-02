from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from scrapers.findwork import FindWorkScraper

FIXTURE = Path(__file__).parent / "fixtures" / "findwork_jobs.json"


@patch("scrapers.findwork.requests.get")
def test_findwork_filters_by_role_or_keywords(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mock_get.return_value = resp

    results = FindWorkScraper().search(["django"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Acme FindWork"
    assert results[0].source == "FindWork.dev"
