from unittest.mock import patch, MagicMock

from scrapers.linkedin import LinkedinScraper

LINKEDIN_HTML = """
<ul>
  <li>
    <h3 class="base-search-card__title">Python Developer</h3>
    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123?refid=abc"></a>
    <h4 class="base-search-card__subtitle">Acme Corp</h4>
    <span class="job-search-card__location">Istanbul, Turkey</span>
  </li>
</ul>
"""


@patch("scrapers.linkedin.get_with_retry")
def test_linkedin_parses_single_page_of_results(mock_get):
    resp = MagicMock(status_code=200, text=LINKEDIN_HTML)
    empty_resp = MagicMock(status_code=200, text="<ul></ul>")
    mock_get.side_effect = [resp, empty_resp]

    results = LinkedinScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].title == "Python Developer"
    assert results[0].company == "Acme Corp"
    assert results[0].url == "https://www.linkedin.com/jobs/view/123"
    assert results[0].source == "LinkedIn"


@patch("scrapers.linkedin.get_with_retry")
def test_linkedin_stops_when_request_fails(mock_get):
    mock_get.return_value = None
    assert LinkedinScraper().search(["python"]) == []
