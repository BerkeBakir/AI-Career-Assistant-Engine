from unittest.mock import patch, MagicMock

from scrapers.bing import BingScraper

BING_HTML = """
<ol>
  <li class="b_algo">
    <a href="https://www.linkedin.com/jobs/view/999">Python Developer - Acme Corp</a>
  </li>
  <li class="b_algo">
    <a href="https://example.com/not-a-job-site">Unrelated result</a>
  </li>
</ol>
"""


@patch("scrapers.bing.get_with_retry")
def test_bing_keeps_only_linkedin_and_indeed_links(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text=BING_HTML)
    results = BingScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].url == "https://www.linkedin.com/jobs/view/999"
    assert results[0].source == "LinkedIn (Bing)"


@patch("scrapers.bing.get_with_retry")
def test_bing_returns_empty_list_when_request_fails(mock_get):
    mock_get.return_value = None
    assert BingScraper().search(["python"]) == []
