from unittest.mock import patch, MagicMock

from scrapers.ddg_fallback import DdgFallbackScraper


@patch("scrapers.ddg_fallback.DDGS")
def test_ddg_fallback_labels_kariyer_and_secretcv_results_by_domain(mock_ddgs_cls):
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = [
        {"href": "https://www.kariyer.net/is-ilani/python-developer-123", "title": "Python Developer - Acme", "body": "İş tanımı..."},
        {"href": "https://www.secretcv.com/is-ilani/456", "title": "Python Developer | Beta", "body": "İş tanımı..."},
        {"href": "https://not-a-real-site.com/page", "title": "Irrelevant", "body": ""},
    ]
    mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs

    results = DdgFallbackScraper().search(["python"], limit=10)
    sources = {r.source for r in results}
    assert "Kariyer.net" in sources
    assert "SecretCV" in sources


@patch("scrapers.ddg_fallback.DDGS")
def test_ddg_fallback_returns_empty_list_on_exception(mock_ddgs_cls):
    mock_ddgs_cls.side_effect = Exception("boom")
    assert DdgFallbackScraper().search(["python"]) == []
