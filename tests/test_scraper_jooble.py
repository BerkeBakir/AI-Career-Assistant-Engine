from unittest.mock import patch, MagicMock

from scrapers.jooble import JoobleScraper


def test_jooble_returns_empty_list_when_no_api_key(monkeypatch):
    monkeypatch.delenv("JOOBLE_API_KEY", raising=False)
    assert JoobleScraper().search(["python"]) == []


@patch("scrapers.jooble.requests.post")
def test_jooble_parses_results_when_key_present(mock_post, monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "test-key-123")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "jobs": [
            {"title": "Python Developer", "company": "Acme", "link": "https://jooble.org/jdp/1", "location": "Istanbul, Turkey", "snippet": "desc"},
        ]
    }
    mock_post.return_value = resp

    results = JoobleScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Acme"
    assert results[0].source == "Jooble"

    call_url = mock_post.call_args[0][0]
    assert "test-key-123" in call_url


@patch("scrapers.jooble.requests.post")
def test_jooble_returns_empty_list_on_non_200(mock_post, monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "test-key-123")
    mock_post.return_value = MagicMock(status_code=401)
    assert JoobleScraper().search(["python"]) == []
