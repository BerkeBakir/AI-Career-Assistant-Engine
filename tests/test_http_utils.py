from unittest.mock import patch, MagicMock

import requests

from scrapers.http_utils import get_with_retry, USER_AGENTS


def test_user_agents_pool_has_multiple_entries():
    assert len(USER_AGENTS) >= 3


@patch("scrapers.http_utils.requests.get")
def test_get_with_retry_returns_response_on_first_success(mock_get):
    ok_resp = MagicMock(status_code=200)
    mock_get.return_value = ok_resp
    result = get_with_retry("https://example.com")
    assert result is ok_resp
    assert mock_get.call_count == 1


@patch("scrapers.http_utils.time.sleep", return_value=None)
@patch("scrapers.http_utils.requests.get")
def test_get_with_retry_retries_once_on_5xx_then_succeeds(mock_get, mock_sleep):
    fail_resp = MagicMock(status_code=503)
    ok_resp = MagicMock(status_code=200)
    mock_get.side_effect = [fail_resp, ok_resp]
    result = get_with_retry("https://example.com", attempts=2)
    assert result is ok_resp
    assert mock_get.call_count == 2


@patch("scrapers.http_utils.time.sleep", return_value=None)
@patch("scrapers.http_utils.requests.get")
def test_get_with_retry_returns_none_after_exhausting_attempts(mock_get, mock_sleep):
    mock_get.side_effect = requests.exceptions.ConnectionError("boom")
    result = get_with_retry("https://example.com", attempts=2)
    assert result is None
    assert mock_get.call_count == 2


@patch("scrapers.http_utils.requests.get")
def test_get_with_retry_uses_random_user_agent_header(mock_get):
    mock_get.return_value = MagicMock(status_code=200)
    get_with_retry("https://example.com")
    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["User-Agent"] in USER_AGENTS
