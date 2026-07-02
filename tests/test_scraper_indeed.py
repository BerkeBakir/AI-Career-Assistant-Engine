from unittest.mock import patch, MagicMock

from scrapers.indeed import IndeedScraper

INDEED_HTML = """
<div class="job_seen_beacon">
  <h2 class="jobTitle">Python Developer</h2>
  <a href="/rc/clk?jk=abc123"></a>
  <span data-testid="company-name">Acme Corp</span>
  <div data-testid="text-location">Istanbul</div>
</div>
"""


@patch("scrapers.indeed.get_with_retry")
def test_indeed_parses_job_cards(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text=INDEED_HTML)
    results = IndeedScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].title == "Python Developer"
    assert results[0].company == "Acme Corp"
    assert results[0].url == "https://tr.indeed.com/rc/clk?jk=abc123"
    assert results[0].source == "Indeed"


@patch("scrapers.indeed.get_with_retry")
def test_indeed_returns_empty_list_when_request_fails(mock_get):
    mock_get.return_value = None
    assert IndeedScraper().search(["python"]) == []
