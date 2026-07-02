from scrapers.base import JobListing


def test_dedupe_key_strips_query_string_and_trailing_slash():
    a = JobListing(title="Python Dev", company="Acme", url="https://example.com/jobs/123/?utm_source=x", source="Test")
    b = JobListing(title="Python Dev (different casing)", company="Acme", url="https://EXAMPLE.com/jobs/123/", source="Test")
    assert a.dedupe_key() == b.dedupe_key()


def test_dedupe_key_differs_for_different_paths():
    a = JobListing(title="A", company="Acme", url="https://example.com/jobs/123", source="Test")
    b = JobListing(title="B", company="Acme", url="https://example.com/jobs/456", source="Test")
    assert a.dedupe_key() != b.dedupe_key()


def test_joblisting_defaults():
    j = JobListing(title="A", company="Acme", url="https://example.com/j/1", source="Test")
    assert j.description == ""
    assert j.location == ""
