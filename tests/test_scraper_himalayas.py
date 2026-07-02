from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from scrapers.himalayas import HimalayasScraper

FIXTURE = Path(__file__).parent / "fixtures" / "himalayas_jobs.json"


@patch("scrapers.himalayas.requests.get")
def test_himalayas_filters_by_title_keyword(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mock_get.return_value = resp

    results = HimalayasScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].url == "https://himalayas.app/jobs/python-engineer-1"
    assert results[0].source == "Himalayas"
