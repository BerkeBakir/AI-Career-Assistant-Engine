from unittest.mock import patch

from functions import url_den_ilan_cek


@patch("functions.trafilatura.extract")
@patch("functions.trafilatura.fetch_url")
def test_url_den_ilan_cek_returns_extracted_text(mock_fetch, mock_extract):
    mock_fetch.return_value = "<html>...</html>"
    mock_extract.return_value = "Bu bir iş ilanı metnidir. " * 10

    metin, hata = url_den_ilan_cek("example.com/ilan")

    assert hata is None
    assert "iş ilanı" in metin
    mock_fetch.assert_called_once_with("https://example.com/ilan")


@patch("functions.trafilatura.fetch_url")
def test_url_den_ilan_cek_returns_error_when_fetch_fails(mock_fetch):
    mock_fetch.return_value = None
    metin, hata = url_den_ilan_cek("example.com/ilan")
    assert metin is None
    assert hata == "Siteye erişilemedi."


@patch("functions.trafilatura.extract")
@patch("functions.trafilatura.fetch_url")
def test_url_den_ilan_cek_returns_error_when_content_too_short(mock_fetch, mock_extract):
    mock_fetch.return_value = "<html>...</html>"
    mock_extract.return_value = "kısa"
    metin, hata = url_den_ilan_cek("example.com/ilan")
    assert metin is None
    assert hata == "İçerik boş."


@patch("functions.trafilatura.fetch_url")
def test_url_den_ilan_cek_prepends_https_when_missing(mock_fetch):
    mock_fetch.return_value = None
    url_den_ilan_cek("example.com/ilan")
    mock_fetch.assert_called_once_with("https://example.com/ilan")
