from unittest.mock import patch, MagicMock

import requests

from scoring import gemini_client


def _mock_response(status=200, body=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body or {}
    return resp


@patch("scoring.gemini_client.requests.post")
def test_gomlemesi_al_returns_vector_on_success(mock_post):
    mock_post.return_value = _mock_response(200, {"embedding": {"values": [0.1, 0.2, 0.3]}})
    sonuc = gemini_client._gemini_gomlemesi_al("Python")
    assert sonuc == [0.1, 0.2, 0.3]


@patch("scoring.gemini_client.requests.post")
def test_gomlemesi_al_returns_none_on_non_200(mock_post):
    mock_post.return_value = _mock_response(500, {})
    assert gemini_client._gemini_gomlemesi_al("Python") is None


@patch("scoring.gemini_client.requests.post")
def test_gomlemesi_al_returns_none_on_request_exception(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("boom")
    assert gemini_client._gemini_gomlemesi_al("Python") is None


def test_gomlemesi_al_returns_none_for_empty_text():
    assert gemini_client._gemini_gomlemesi_al("") is None
    assert gemini_client._gemini_gomlemesi_al("   ") is None
