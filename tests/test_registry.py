from scrapers.registry import get_active_scrapers


def test_registry_includes_all_always_on_scrapers():
    names = {s.name for s in get_active_scrapers()}
    expected = {
        "LinkedIn", "Indeed", "Bing", "Arbeitnow", "Remotive", "Himalayas",
        "FindWork.dev", "RemoteOK", "WeWorkRemotely", "Yenibiris", "Eleman.net",
        "DDG Discovery",
    }
    assert expected.issubset(names)


def test_registry_excludes_jooble_without_api_key(monkeypatch):
    monkeypatch.delenv("JOOBLE_API_KEY", raising=False)
    names = {s.name for s in get_active_scrapers()}
    assert "Jooble" not in names


def test_registry_includes_jooble_with_api_key(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "test-key")
    names = {s.name for s in get_active_scrapers()}
    assert "Jooble" in names
