from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from scrapers.remotive import RemotiveScraper

FIXTURE = Path(__file__).parent / "fixtures" / "remotive_jobs.json"


@patch("scrapers.remotive.requests.get")
def test_remotive_filters_by_title_keyword(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mock_get.return_value = resp

    results = RemotiveScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Acme Co"
    assert results[0].source == "Remotive"
