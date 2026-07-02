import time
from unittest.mock import MagicMock, patch

from scrapers.base import JobListing
import job_search_service


def _fake_scraper(name, listings, raises=False):
    scraper = MagicMock()
    scraper.name = name
    if raises:
        scraper.search.side_effect = RuntimeError("scraper kirildi")
    else:
        scraper.search.return_value = listings
    return scraper


@patch("job_search_service.get_active_scrapers")
def test_search_jobs_merges_results_from_all_scrapers(mock_get_scrapers):
    mock_get_scrapers.return_value = [
        _fake_scraper("A", [JobListing(title="Job1", company="C1", url="https://a.com/1", source="A")]),
        _fake_scraper("B", [JobListing(title="Job2", company="C2", url="https://b.com/2", source="B")]),
    ]
    results = job_search_service.search_jobs(["python"])
    assert len(results) == 2
    assert {r["kaynak"] for r in results} == {"A", "B"}
    assert results[0]["baslik"] in {"Job1", "Job2"}


@patch("job_search_service.get_active_scrapers")
def test_search_jobs_deduplicates_by_normalized_url(mock_get_scrapers):
    mock_get_scrapers.return_value = [
        _fake_scraper("A", [JobListing(title="Job1", company="C1", url="https://a.com/1?utm=x", source="A")]),
        _fake_scraper("B", [JobListing(title="Job1 dup", company="C1", url="https://a.com/1/", source="B")]),
    ]
    results = job_search_service.search_jobs(["python"])
    assert len(results) == 1


@patch("job_search_service.get_active_scrapers")
def test_search_jobs_skips_scraper_that_raises_and_keeps_others(mock_get_scrapers):
    mock_get_scrapers.return_value = [
        _fake_scraper("Broken", [], raises=True),
        _fake_scraper("Good", [JobListing(title="Job1", company="C1", url="https://a.com/1", source="Good")]),
    ]
    results = job_search_service.search_jobs(["python"])
    assert len(results) == 1
    assert results[0]["kaynak"] == "Good"


@patch("job_search_service.get_active_scrapers")
def test_search_jobs_returns_dict_shape_expected_by_app(mock_get_scrapers):
    mock_get_scrapers.return_value = [
        _fake_scraper("A", [JobListing(title="Job1", company="C1", url="https://a.com/1", source="A", description="d", location="Istanbul")]),
    ]
    results = job_search_service.search_jobs(["python"])
    assert set(results[0].keys()) == {"baslik", "link", "sirket", "kaynak", "aciklama"}
    assert results[0]["baslik"] == "Job1"
    assert results[0]["link"] == "https://a.com/1"
    assert results[0]["sirket"] == "C1"
    assert results[0]["kaynak"] == "A"


def _slow_scraper(name, delay_seconds, listings):
    scraper = MagicMock()
    scraper.name = name

    def _search(keywords, limit=20):
        time.sleep(delay_seconds)
        return listings

    scraper.search.side_effect = _search
    return scraper


@patch("job_search_service.get_active_scrapers")
def test_search_jobs_bounds_wall_clock_time_to_per_scraper_timeout(mock_get_scrapers):
    # One scraper hangs far longer than the timeout; a fast scraper returns quickly.
    # The whole call must not block on the slow scraper past ~PER_SCRAPER_TIMEOUT.
    mock_get_scrapers.return_value = [
        _slow_scraper("Slow", delay_seconds=2.0, listings=[
            JobListing(title="SlowJob", company="C1", url="https://a.com/slow", source="Slow")
        ]),
        _fake_scraper("Fast", [JobListing(title="FastJob", company="C2", url="https://a.com/fast", source="Fast")]),
    ]
    with patch.object(job_search_service, "PER_SCRAPER_TIMEOUT", 0.3):
        start = time.monotonic()
        results = job_search_service.search_jobs(["python"])
        elapsed = time.monotonic() - start

    assert elapsed < 1.5, f"search_jobs blocked for {elapsed}s, timeout was not enforced"
    assert {r["kaynak"] for r in results} == {"Fast"}
