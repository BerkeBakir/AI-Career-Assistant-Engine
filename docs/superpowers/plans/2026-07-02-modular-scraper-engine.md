# Modüler Scraper Motoru — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sequential, monolithic `functions.py:internette_is_ara()` with a modular `scrapers/` package where each job source is one file, orchestrated in parallel via `ThreadPoolExecutor`, adding real Turkish scrapers and new free API/RSS sources.

**Architecture:** Each scraper is a small class implementing `search(keywords, limit) -> list[JobListing]`. A `registry.py` lists active scrapers. `job_search_service.py` runs them concurrently with per-scraper timeouts, catches failures independently, and dedupes by normalized URL. `app.py` calls `job_search_service.search_jobs()` instead of `functions.internette_is_ara()`.

**Tech Stack:** Python 3, Flask, requests, BeautifulSoup4, pytest, `concurrent.futures.ThreadPoolExecutor` (stdlib, no new dependency for concurrency).

**Scope note:** This is plan 1 of 3 derived from `docs/superpowers/specs/2026-07-02-modular-scraping-engine-design.md`. Plan 2 (deterministic + LLM hybrid match scoring) and Plan 3 (feedback collection + auto-reweighting, depends on Plan 2's `ScoringConfig` table) are separate plan documents, written and executed after this one ships and its tests pass.

## Global Constraints

- Repo root: `C:\Users\Monster\Desktop\AI-Career-Assistant-Engine`
- All new code goes on branch `feature/modular-scraping-engine` (created in Task 1).
- Turkish variable/log-message style matches the existing codebase (e.g. `functions.py`, `app.py` use Turkish identifiers like `metin_cikar`, `ilan`) — keep this convention in new scraper modules' user-facing strings and DB-facing field names, but the `JobListing` dataclass field names (`title`, `company`, `url`, `source`, `description`, `location`) are English since this is a new internal interface, not user-facing Turkish UI text.
- Do not modify `proje.db`, `models.py`, or any template file in this plan — those are out of scope (see spec's "Kapsam dışı" section).
- No live network calls in tests — every scraper test uses a fixture file under `tests/fixtures/` and mocks `requests.get`/`requests.post`.
- Per-scraper HTTP timeout: 10 seconds. Per-scraper overall budget in the orchestrator: 12 seconds (`future.result(timeout=12)`).
- Commit after every task passes its tests.

---

### Task 1: Branch setup + `JobListing` dataclass and `BaseScraper` interface

**Files:**
- Create: `scrapers/__init__.py` (empty, makes `scrapers` a package)
- Create: `scrapers/base.py`
- Test: `tests/test_scrapers_base.py`

**Interfaces:**
- Produces: `JobListing` dataclass with fields `title: str, company: str, url: str, source: str, description: str = "", location: str = ""`. `JobListing.dedupe_key() -> str` returns the URL with query string and trailing slash stripped, lowercased scheme+host.
- Produces: `BaseScraper` ABC with `name: str` class attribute and abstract method `search(self, keywords: list[str], limit: int = 20) -> list[JobListing]`.

- [ ] **Step 1: Create the feature branch**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && git checkout -b feature/modular-scraping-engine`
Expected: `Switched to a new branch 'feature/modular-scraping-engine'`

- [ ] **Step 2: Write the failing test for `JobListing.dedupe_key`**

Create `tests/test_scrapers_base.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scrapers_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers'`

- [ ] **Step 4: Create the package and implement `base.py`**

Create `scrapers/__init__.py` (empty file).

Create `scrapers/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class JobListing:
    title: str
    company: str
    url: str
    source: str
    description: str = ""
    location: str = ""

    def dedupe_key(self) -> str:
        parsed = urlparse(self.url)
        path = parsed.path.rstrip('/')
        return f"{parsed.netloc.lower()}{path}"


class BaseScraper(ABC):
    name: str = "BaseScraper"

    @abstractmethod
    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        raise NotImplementedError
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scrapers_base.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/__init__.py scrapers/base.py tests/test_scrapers_base.py
git commit -m "feat: add JobListing dataclass and BaseScraper interface"
```

---

### Task 2: RemoteOK scraper (new source, JSON API)

**Files:**
- Create: `scrapers/remoteok.py`
- Test: `tests/test_scraper_remoteok.py`
- Fixture (already exists): `tests/fixtures/remoteok_jobs.json`

**Interfaces:**
- Consumes: `scrapers.base.JobListing`, `scrapers.base.BaseScraper` (Task 1).
- Produces: `RemoteOkScraper` class, `name = "RemoteOK"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_scraper_remoteok.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.remoteok import RemoteOkScraper

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok_jobs.json"


def _mock_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return resp


@patch("scrapers.remoteok.requests.get")
def test_remoteok_skips_legal_notice_entry(mock_get):
    mock_get.return_value = _mock_response()
    results = RemoteOkScraper().search(["python"], limit=10)
    assert all(r.title for r in results)


@patch("scrapers.remoteok.requests.get")
def test_remoteok_filters_by_keyword_in_title_or_tags(mock_get):
    mock_get.return_value = _mock_response()
    results = RemoteOkScraper().search(["react"], limit=10)
    assert len(results) == 1
    assert results[0].title == "React Engineer"
    assert results[0].company == "Beta Inc"
    assert results[0].url == "https://remoteOK.com/remote-jobs/remote-react-engineer-beta-1134361"
    assert results[0].source == "RemoteOK"


@patch("scrapers.remoteok.requests.get")
def test_remoteok_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 500
    mock_get.return_value = resp
    assert RemoteOkScraper().search(["python"]) == []


@patch("scrapers.remoteok.requests.get")
def test_remoteok_returns_empty_list_on_exception(mock_get):
    mock_get.side_effect = ConnectionError("boom")
    assert RemoteOkScraper().search(["python"]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_remoteok.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.remoteok'`

- [ ] **Step 3: Implement `scrapers/remoteok.py`**

```python
import logging

import requests

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class RemoteOkScraper(BaseScraper):
    name = "RemoteOK"
    API_URL = "https://remoteok.com/api"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            resp = requests.get(self.API_URL, headers=headers, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"RemoteOK istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            logger.warning(f"RemoteOK beklenmeyen durum kodu: {resp.status_code}")
            return []

        jobs = resp.json()
        keywords_lower = [k.lower() for k in keywords]
        results = []
        for job in jobs:
            position = job.get("position")
            if not position:
                continue
            title_lower = position.lower()
            tags = [t.lower() for t in job.get("tags", [])]
            if any(k in title_lower for k in keywords_lower) or any(k in tags for k in keywords_lower):
                results.append(JobListing(
                    title=position,
                    company=job.get("company", "RemoteOK"),
                    url=job.get("url", ""),
                    source=self.name,
                    description=job.get("description", "")[:300],
                    location=job.get("location", "Remote"),
                ))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_remoteok.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/remoteok.py tests/test_scraper_remoteok.py
git commit -m "feat: add RemoteOK scraper"
```

---

### Task 3: WeWorkRemotely scraper (new source, RSS/XML)

**Files:**
- Create: `scrapers/weworkremotely.py`
- Test: `tests/test_scraper_weworkremotely.py`
- Fixture (already exists): `tests/fixtures/weworkremotely.xml`

**Interfaces:**
- Consumes: `scrapers.base.JobListing`, `scrapers.base.BaseScraper` (Task 1).
- Produces: `WeWorkRemotelyScraper` class, `name = "WeWorkRemotely"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_scraper_weworkremotely.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.weworkremotely import WeWorkRemotelyScraper

FIXTURE = Path(__file__).parent / "fixtures" / "weworkremotely.xml"


def _mock_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.content = FIXTURE.read_bytes()
    return resp


@patch("scrapers.weworkremotely.requests.get")
def test_wwr_parses_title_company_from_colon_format(mock_get):
    mock_get.return_value = _mock_response()
    results = WeWorkRemotelyScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Acme Corp"
    assert results[0].title == "Senior Python Developer"
    assert results[0].url == "https://weworkremotely.com/remote-jobs/acme-corp-senior-python-developer"
    assert results[0].source == "WeWorkRemotely"


@patch("scrapers.weworkremotely.requests.get")
def test_wwr_matches_react_keyword(mock_get):
    mock_get.return_value = _mock_response()
    results = WeWorkRemotelyScraper().search(["react"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Beta Inc"


@patch("scrapers.weworkremotely.requests.get")
def test_wwr_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 404
    mock_get.return_value = resp
    assert WeWorkRemotelyScraper().search(["python"]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_weworkremotely.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.weworkremotely'`

- [ ] **Step 3: Implement `scrapers/weworkremotely.py`**

RSS `<title>` entries follow the `Company: Job Title` convention used by WWR. Parse with `BeautifulSoup`'s `xml` parser (already available via `beautifulsoup4` + stdlib `xml` fallback — no `lxml` needed, `html.parser` can also read simple RSS since it's well-formed XML with no self-closing edge cases here, but use `"xml"` if `lxml` is installed, falling back to `"html.parser"`).

```python
import logging

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class WeWorkRemotelyScraper(BaseScraper):
    name = "WeWorkRemotely"
    RSS_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            resp = requests.get(self.RSS_URL, headers=headers, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"WeWorkRemotely istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            logger.warning(f"WeWorkRemotely beklenmeyen durum kodu: {resp.status_code}")
            return []

        try:
            soup = BeautifulSoup(resp.content, "xml")
        except Exception:
            soup = BeautifulSoup(resp.content, "html.parser")

        keywords_lower = [k.lower() for k in keywords]
        results = []
        for item in soup.find_all("item"):
            raw_title = item.find("title").get_text(strip=True) if item.find("title") else ""
            link = item.find("link").get_text(strip=True) if item.find("link") else ""
            if not raw_title or not link:
                continue

            if ":" in raw_title:
                company, _, job_title = raw_title.partition(":")
                company = company.strip()
                job_title = job_title.strip()
            else:
                company, job_title = "WeWorkRemotely", raw_title

            if not any(k in job_title.lower() for k in keywords_lower):
                continue

            region = item.find("region").get_text(strip=True) if item.find("region") else "Remote"
            results.append(JobListing(
                title=job_title,
                company=company,
                url=link,
                source=self.name,
                description="",
                location=region,
            ))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_weworkremotely.py -v`
Expected: `3 passed`

If it fails with an XML parser error, run `pip install lxml` and re-run — `lxml` will be added to `requirements.txt` in Task 13.

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/weworkremotely.py tests/test_scraper_weworkremotely.py
git commit -m "feat: add WeWorkRemotely RSS scraper"
```

---

### Task 4: Yenibiris.com scraper (new real Turkish scraper)

Verified live on 2026-07-02: `https://www.yenibiris.com/is-ilanlari?q=<keyword>` returns 200 with server-rendered listings. Each listing's title+link is `a.gtmTitle` (has `data-ad-id` and `href`); the matching company name is `div.jobCompanyLnk[data-ad-id=...]` with the same `data-ad-id`.

**Files:**
- Create: `scrapers/yenibiris.py`
- Test: `tests/test_scraper_yenibiris.py`
- Fixture (already exists): `tests/fixtures/yenibiris_search.html`

**Interfaces:**
- Consumes: `scrapers.base.JobListing`, `scrapers.base.BaseScraper` (Task 1).
- Produces: `YenibirisScraper` class, `name = "Yenibiris"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_scraper_yenibiris.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.yenibiris import YenibirisScraper

FIXTURE = Path(__file__).parent / "fixtures" / "yenibiris_search.html"


def _mock_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.content = FIXTURE.read_bytes()
    return resp


@patch("scrapers.yenibiris.requests.get")
def test_yenibiris_extracts_title_link_and_matching_company(mock_get):
    mock_get.return_value = _mock_response()
    results = YenibirisScraper().search(["yazılım"], limit=10)
    assert len(results) == 1
    r = results[0]
    assert r.title == "Yazılım Geliştirici"
    assert r.company == "Frigo Soğutma San Tic A.Ş"
    assert r.url == "https://www.yenibiris.com/is-ilani/yazilim-gelistirici/1210713"
    assert r.source == "Yenibiris"


@patch("scrapers.yenibiris.requests.get")
def test_yenibiris_matches_second_listing_by_different_keyword(mock_get):
    mock_get.return_value = _mock_response()
    results = YenibirisScraper().search(["backend"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Wanda Vista İstanbul"


@patch("scrapers.yenibiris.requests.get")
def test_yenibiris_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 403
    mock_get.return_value = resp
    assert YenibirisScraper().search(["python"]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_yenibiris.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.yenibiris'`

- [ ] **Step 3: Implement `scrapers/yenibiris.py`**

```python
import logging
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class YenibirisScraper(BaseScraper):
    name = "Yenibiris"
    SEARCH_URL = "https://www.yenibiris.com/is-ilanlari?q={query}"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        if not keywords:
            return []
        query = quote(keywords[0])
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9",
        }
        try:
            resp = requests.get(self.SEARCH_URL.format(query=query), headers=headers, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"Yenibiris istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            logger.warning(f"Yenibiris beklenmeyen durum kodu: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        keywords_lower = [k.lower() for k in keywords]
        results = []
        for title_link in soup.select("a.gtmTitle"):
            ad_id = title_link.get("data-ad-id")
            href = title_link.get("href")
            title = title_link.get_text(strip=True)
            if not (ad_id and href and title):
                continue
            if not any(k in title.lower() for k in keywords_lower):
                continue

            company_el = soup.select_one(f'div.jobCompanyLnk[data-ad-id="{ad_id}"]')
            company = company_el.get_text(strip=True) if company_el else "Yenibiris İlanı"

            results.append(JobListing(
                title=title,
                company=company,
                url=href,
                source=self.name,
            ))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_yenibiris.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/yenibiris.py tests/test_scraper_yenibiris.py
git commit -m "feat: add real Yenibiris.com scraper"
```

---

### Task 5: Eleman.net scraper (new real Turkish scraper)

Verified live on 2026-07-02: `https://www.eleman.net/is-ilanlari/<slug>` returns 200 with server-rendered listings. The `.map-job-card` class seen in the raw HTML is a JS-populated map template with zero real entries — ignore it. Real listings are `a[href*="/is-ilani/"]`, each containing `h3.c-showcase-box__title` (title, may have a trailing icon `<span>` to strip) and `span.c-showcase-box__subtitle` (text is `"Company - [icon] Location"`, split on `" - "`).

**Files:**
- Create: `scrapers/eleman.py`
- Test: `tests/test_scraper_eleman.py`
- Fixture (already exists): `tests/fixtures/eleman_search.html`

**Interfaces:**
- Consumes: `scrapers.base.JobListing`, `scrapers.base.BaseScraper` (Task 1).
- Produces: `ElemanScraper` class, `name = "Eleman.net"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_scraper_eleman.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.eleman import ElemanScraper

FIXTURE = Path(__file__).parent / "fixtures" / "eleman_search.html"


def _mock_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.content = FIXTURE.read_bytes()
    return resp


@patch("scrapers.eleman.requests.get")
def test_eleman_extracts_title_stripped_of_phone_icon_span(mock_get):
    mock_get.return_value = _mock_response()
    results = ElemanScraper().search(["yazılım"], limit=10)
    assert len(results) == 1
    r = results[0]
    assert r.title == "Yazılım Geliştirici"
    assert r.url == "https://www.eleman.net/is-ilani/yazilim-gelistirici-i4702359"
    assert r.source == "Eleman.net"


@patch("scrapers.eleman.requests.get")
def test_eleman_splits_company_and_location_from_subtitle(mock_get):
    mock_get.return_value = _mock_response()
    results = ElemanScraper().search(["yazılım"], limit=10)
    r = results[0]
    assert r.company == "Acme Yazılım A.Ş."
    assert "İstanbul Anadolu" in r.location


@patch("scrapers.eleman.requests.get")
def test_eleman_matches_second_listing_by_keyword(mock_get):
    mock_get.return_value = _mock_response()
    results = ElemanScraper().search(["frontend"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Beta Teknoloji Ltd."


@patch("scrapers.eleman.requests.get")
def test_eleman_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 500
    mock_get.return_value = resp
    assert ElemanScraper().search(["python"]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_eleman.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.eleman'`

- [ ] **Step 3: Implement `scrapers/eleman.py`**

```python
import logging
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class ElemanScraper(BaseScraper):
    name = "Eleman.net"
    SEARCH_URL = "https://www.eleman.net/is-ilanlari/{query}"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        if not keywords:
            return []
        slug = quote(keywords[0].lower().replace(" ", "-"))
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9",
        }
        try:
            resp = requests.get(self.SEARCH_URL.format(query=slug), headers=headers, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"Eleman.net istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            logger.warning(f"Eleman.net beklenmeyen durum kodu: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        keywords_lower = [k.lower() for k in keywords]
        results = []
        for card in soup.select('a[href*="/is-ilani/"]'):
            title_el = card.select_one("h3.c-showcase-box__title")
            subtitle_el = card.select_one("span.c-showcase-box__subtitle")
            href = card.get("href")
            if not (title_el and href):
                continue

            title = title_el.find(string=True, recursive=False)
            title = title.strip() if title else title_el.get_text(strip=True)
            if not title or not any(k in title.lower() for k in keywords_lower):
                continue

            company, location = "Eleman.net İlanı", ""
            if subtitle_el:
                subtitle_text = subtitle_el.get_text(" ", strip=True)
                parts = [p.strip() for p in subtitle_text.split(" - ") if p.strip()]
                if parts:
                    company = parts[0]
                if len(parts) > 1:
                    location = parts[1]

            results.append(JobListing(
                title=title,
                company=company,
                url=href,
                source=self.name,
                location=location,
            ))
            if len(results) >= limit:
                break
        return results
```

Note on `title_el.find(string=True, recursive=False)`: the `<h3>` contains the title text plus a nested `<span>` icon (see fixture) — `find(string=True, recursive=False)` grabs only the direct text node, not the icon span's text, so titles come out clean without falling back to string-splitting on the phone icon markup.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_eleman.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/eleman.py tests/test_scraper_eleman.py
git commit -m "feat: add real Eleman.net scraper"
```

---

### Task 6: Port existing JSON-API sources (Arbeitnow, Remotive, Himalayas, FindWork.dev)

These four already work today inside `functions.py:internette_is_ara()` (lines 358-450 of the current `functions.py` on `main`, before this branch's changes) — this task ports their existing, working logic into the new one-file-per-scraper shape unchanged, so no behavior regression.

**Files:**
- Create: `scrapers/arbeitnow.py`, `scrapers/remotive.py`, `scrapers/himalayas.py`, `scrapers/findwork.py`
- Test: `tests/test_scraper_arbeitnow.py`, `tests/test_scraper_remotive.py`, `tests/test_scraper_himalayas.py`, `tests/test_scraper_findwork.py`
- Fixtures: create `tests/fixtures/arbeitnow_jobs.json`, `tests/fixtures/remotive_jobs.json`, `tests/fixtures/himalayas_jobs.json`, `tests/fixtures/findwork_jobs.json`

**Interfaces:**
- Consumes: `scrapers.base.JobListing`, `scrapers.base.BaseScraper` (Task 1).
- Produces: `ArbeitnowScraper` (`name = "Arbeitnow"`), `RemotiveScraper` (`name = "Remotive"`), `HimalayasScraper` (`name = "Himalayas"`), `FindWorkScraper` (`name = "FindWork.dev"`).

- [ ] **Step 1: Create the four fixture files**

Create `tests/fixtures/arbeitnow_jobs.json`:

```json
{
  "data": [
    {"title": "Python Backend Developer", "company_name": "Acme Remote", "url": "https://www.arbeitnow.com/jobs/companies/acme/python-backend-developer-1", "location": "Remote", "tags": ["python", "backend"]},
    {"title": "React Frontend Developer", "company_name": "Beta Remote", "url": "https://www.arbeitnow.com/jobs/companies/beta/react-frontend-developer-2", "location": "Remote", "tags": ["react", "frontend"]}
  ]
}
```

Create `tests/fixtures/remotive_jobs.json`:

```json
{
  "jobs": [
    {"title": "Python Developer", "company_name": "Acme Co", "url": "https://remotive.com/remote-jobs/software-dev/python-developer-1", "candidate_required_location": "Worldwide"},
    {"title": "Marketing Manager", "company_name": "Gamma Co", "url": "https://remotive.com/remote-jobs/marketing/marketing-manager-2", "candidate_required_location": "USA"}
  ]
}
```

Create `tests/fixtures/himalayas_jobs.json`:

```json
{
  "jobs": [
    {"title": "Python Engineer", "companyName": "Acme Himalayas", "applicationLink": "https://himalayas.app/jobs/python-engineer-1", "slug": "python-engineer-1", "locationRestrictions": "Worldwide"},
    {"title": "Sales Representative", "companyName": "Delta Himalayas", "applicationLink": "https://himalayas.app/jobs/sales-representative-2", "slug": "sales-representative-2", "locationRestrictions": "USA"}
  ]
}
```

Create `tests/fixtures/findwork_jobs.json`:

```json
{
  "results": [
    {"role": "Python Developer", "company_name": "Acme FindWork", "url": "https://findwork.dev/jobs/python-developer-1", "location": "Remote", "keywords": ["python", "django"]},
    {"role": "UX Designer", "company_name": "Epsilon FindWork", "url": "https://findwork.dev/jobs/ux-designer-2", "location": "Remote", "keywords": ["figma", "design"]}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_scraper_arbeitnow.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from scrapers.arbeitnow import ArbeitnowScraper

FIXTURE = Path(__file__).parent / "fixtures" / "arbeitnow_jobs.json"


@patch("scrapers.arbeitnow.requests.get")
def test_arbeitnow_filters_by_title_keyword(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mock_get.return_value = resp

    results = ArbeitnowScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Acme Remote"
    assert results[0].source == "Arbeitnow"


@patch("scrapers.arbeitnow.requests.get")
def test_arbeitnow_returns_empty_list_on_non_200(mock_get):
    resp = MagicMock()
    resp.status_code = 500
    mock_get.return_value = resp
    assert ArbeitnowScraper().search(["python"]) == []
```

Create `tests/test_scraper_remotive.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from scrapers.remotive import RemotiveScraper

FIXTURE = Path(__file__).parent / "fixtures" / "remotive_jobs.json"


@patch("scrapers.remotive.requests.get")
def test_remotive_filters_by_title_keyword(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mock_get.return_value = resp

    results = RemotiveScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Acme Co"
    assert results[0].source == "Remotive"
```

Create `tests/test_scraper_himalayas.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from scrapers.himalayas import HimalayasScraper

FIXTURE = Path(__file__).parent / "fixtures" / "himalayas_jobs.json"


@patch("scrapers.himalayas.requests.get")
def test_himalayas_filters_by_title_keyword(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mock_get.return_value = resp

    results = HimalayasScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].url == "https://himalayas.app/jobs/python-engineer-1"
    assert results[0].source == "Himalayas"
```

Create `tests/test_scraper_findwork.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from scrapers.findwork import FindWorkScraper

FIXTURE = Path(__file__).parent / "fixtures" / "findwork_jobs.json"


@patch("scrapers.findwork.requests.get")
def test_findwork_filters_by_role_or_keywords(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mock_get.return_value = resp

    results = FindWorkScraper().search(["django"], limit=10)
    assert len(results) == 1
    assert results[0].company == "Acme FindWork"
    assert results[0].source == "FindWork.dev"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_arbeitnow.py tests/test_scraper_remotive.py tests/test_scraper_himalayas.py tests/test_scraper_findwork.py -v`
Expected: FAIL — 4x `ModuleNotFoundError`

- [ ] **Step 4: Implement `scrapers/arbeitnow.py`**

```python
import logging

import requests

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class ArbeitnowScraper(BaseScraper):
    name = "Arbeitnow"
    API_URL = "https://www.arbeitnow.com/api/job-board-api"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        try:
            resp = requests.get(self.API_URL, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"Arbeitnow istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            return []

        keywords_lower = [k.lower() for k in keywords]
        results = []
        for job in resp.json().get("data", []):
            title = job.get("title", "")
            if not any(k in title.lower() for k in keywords_lower):
                continue
            results.append(JobListing(
                title=title,
                company=job.get("company_name", "Arbeitnow"),
                url=job.get("url", ""),
                source=self.name,
                location=job.get("location", "Remote"),
                description=", ".join(job.get("tags", [])[:3]),
            ))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 5: Implement `scrapers/remotive.py`**

```python
import logging

import requests

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class RemotiveScraper(BaseScraper):
    name = "Remotive"
    API_URL = "https://remotive.com/api/remote-jobs?limit=50"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        try:
            resp = requests.get(self.API_URL, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"Remotive istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            return []

        keywords_lower = [k.lower() for k in keywords]
        results = []
        for job in resp.json().get("jobs", []):
            title = job.get("title", "")
            title_lower = title.lower()
            if not (any(k in title_lower for k in keywords_lower) or "developer" in title_lower or "engineer" in title_lower):
                continue
            results.append(JobListing(
                title=title,
                company=job.get("company_name", "Remotive"),
                url=job.get("url", ""),
                source=self.name,
                location=f"Remote - {job.get('candidate_required_location', 'Worldwide')}",
            ))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 6: Implement `scrapers/himalayas.py`**

```python
import logging

import requests

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class HimalayasScraper(BaseScraper):
    name = "Himalayas"
    API_URL = "https://himalayas.app/jobs/api?limit=30"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        try:
            resp = requests.get(self.API_URL, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"Himalayas istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            return []

        keywords_lower = [k.lower() for k in keywords]
        results = []
        for job in resp.json().get("jobs", []):
            title = job.get("title", "")
            if not any(k in title.lower() for k in keywords_lower):
                continue
            url = job.get("applicationLink") or f"https://himalayas.app/jobs/{job.get('slug', '')}"
            results.append(JobListing(
                title=title,
                company=job.get("companyName", "Himalayas"),
                url=url,
                source=self.name,
                location=f"Remote - {job.get('locationRestrictions', 'Worldwide')}",
            ))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 7: Implement `scrapers/findwork.py`**

```python
import logging

import requests

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class FindWorkScraper(BaseScraper):
    name = "FindWork.dev"
    API_URL = "https://findwork.dev/api/jobs/"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        try:
            resp = requests.get(self.API_URL, headers={"Accept": "application/json"}, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"FindWork.dev istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            return []

        keywords_lower = [k.lower() for k in keywords]
        results = []
        for job in resp.json().get("results", []):
            role = job.get("role", "")
            role_lower = role.lower()
            job_keywords = str(job.get("keywords", [])).lower()
            if not (any(k in role_lower for k in keywords_lower) or any(k in job_keywords for k in keywords_lower)):
                continue
            results.append(JobListing(
                title=role,
                company=job.get("company_name", "FindWork"),
                url=job.get("url", ""),
                source=self.name,
                location=job.get("location", "Remote"),
                description=", ".join(job.get("keywords", [])[:3]),
            ))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_arbeitnow.py tests/test_scraper_remotive.py tests/test_scraper_himalayas.py tests/test_scraper_findwork.py -v`
Expected: `5 passed`

- [ ] **Step 9: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/arbeitnow.py scrapers/remotive.py scrapers/himalayas.py scrapers/findwork.py tests/test_scraper_arbeitnow.py tests/test_scraper_remotive.py tests/test_scraper_himalayas.py tests/test_scraper_findwork.py tests/fixtures/arbeitnow_jobs.json tests/fixtures/remotive_jobs.json tests/fixtures/himalayas_jobs.json tests/fixtures/findwork_jobs.json
git commit -m "feat: port Arbeitnow, Remotive, Himalayas, FindWork.dev to scraper modules"
```

---

### Task 7: Shared UA-rotation/retry helper + hardened LinkedIn scraper

The current LinkedIn scraper (`functions.py` lines 278-315 on `main`) uses one fixed User-Agent and no retry. This task adds a shared helper both this and Task 8's scrapers use, then ports LinkedIn onto it.

**Files:**
- Create: `scrapers/http_utils.py`
- Create: `scrapers/linkedin.py`
- Test: `tests/test_http_utils.py`, `tests/test_scraper_linkedin.py`

**Interfaces:**
- Produces: `scrapers.http_utils.get_with_retry(url, params=None, headers=None, timeout=10, attempts=2) -> requests.Response | None`. Picks a random User-Agent from `USER_AGENTS` each call, retries once with backoff (`time.sleep(1)`) on `requests.RequestException` or HTTP 5xx, returns `None` if all attempts fail.
- Produces: `LinkedinScraper` class, `name = "LinkedIn"`, using `get_with_retry`.

- [ ] **Step 1: Write the failing test for `http_utils`**

Create `tests/test_http_utils.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_http_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.http_utils'`

- [ ] **Step 3: Implement `scrapers/http_utils.py`**

```python
import logging
import random
import time

import requests

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def get_with_retry(url, params=None, headers=None, timeout=10, attempts=2):
    merged_headers = dict(headers or {})
    for attempt in range(1, attempts + 1):
        merged_headers["User-Agent"] = random.choice(USER_AGENTS)
        try:
            resp = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
        except requests.RequestException as e:
            logger.warning(f"HTTP istegi basarisiz (deneme {attempt}/{attempts}): {e}")
            if attempt < attempts:
                time.sleep(1)
            continue

        if resp.status_code < 500:
            return resp

        logger.warning(f"HTTP {resp.status_code} (deneme {attempt}/{attempts}): {url}")
        if attempt < attempts:
            time.sleep(1)

    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_http_utils.py -v`
Expected: `5 passed`

- [ ] **Step 5: Write the failing test for `LinkedinScraper`**

Create `tests/test_scraper_linkedin.py`:

```python
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
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_linkedin.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.linkedin'`

- [ ] **Step 7: Implement `scrapers/linkedin.py`**

Ports the existing logic from `functions.py:internette_is_ara()` (LinkedIn section, `main` branch) onto `get_with_retry`.

```python
import logging

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, JobListing
from scrapers.http_utils import get_with_retry

logger = logging.getLogger(__name__)


class LinkedinScraper(BaseScraper):
    name = "LinkedIn"
    SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        if not keywords:
            return []
        query = keywords[0]
        results = []
        for start_index in [0, 25, 50]:
            params = {"keywords": query, "location": "Turkey", "start": start_index}
            resp = get_with_retry(self.SEARCH_URL, params=params, timeout=self.TIMEOUT)
            if resp is None:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.find_all("li")
            if not items:
                break

            for item in items:
                try:
                    title = item.find("h3", class_="base-search-card__title").get_text(strip=True)
                    link = item.find("a", class_="base-card__full-link").get("href").split("?")[0]
                    company = item.find("h4", class_="base-search-card__subtitle").get_text(strip=True)
                    location_el = item.find("span", class_="job-search-card__location")
                    location = location_el.get_text(strip=True) if location_el else "Türkiye"
                except AttributeError:
                    continue

                results.append(JobListing(title=title, company=company, url=link, source=self.name, location=location))
                if len(results) >= limit:
                    return results
        return results
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_linkedin.py -v`
Expected: `2 passed`

- [ ] **Step 9: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/http_utils.py scrapers/linkedin.py tests/test_http_utils.py tests/test_scraper_linkedin.py
git commit -m "feat: add UA-rotation/retry helper and hardened LinkedIn scraper"
```

---

### Task 8: Hardened Indeed and Bing scrapers

Ports the existing logic from `functions.py:internette_is_ara()` (Indeed section lines 316-356, Bing section lines 528-555 on `main`) onto `get_with_retry` (Task 7).

**Files:**
- Create: `scrapers/indeed.py`, `scrapers/bing.py`
- Test: `tests/test_scraper_indeed.py`, `tests/test_scraper_bing.py`

**Interfaces:**
- Consumes: `scrapers.http_utils.get_with_retry` (Task 7), `scrapers.base.JobListing`/`BaseScraper` (Task 1).
- Produces: `IndeedScraper` (`name = "Indeed"`), `BingScraper` (`name = "Bing"`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scraper_indeed.py`:

```python
from unittest.mock import patch, MagicMock

from scrapers.indeed import IndeedScraper

INDEED_HTML = """
<div class="job_seen_beacon">
  <h2 class="jobTitle">Python Developer</h2>
  <a href="/rc/clk?jk=abc123"></a>
  <span data-testid="company-name">Acme Corp</span>
  <div data-testid="text-location">Istanbul</div>
</div>
"""


@patch("scrapers.indeed.get_with_retry")
def test_indeed_parses_job_cards(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text=INDEED_HTML)
    results = IndeedScraper().search(["python"], limit=10)
    assert len(results) == 1
    assert results[0].title == "Python Developer"
    assert results[0].company == "Acme Corp"
    assert results[0].url == "https://tr.indeed.com/rc/clk?jk=abc123"
    assert results[0].source == "Indeed"


@patch("scrapers.indeed.get_with_retry")
def test_indeed_returns_empty_list_when_request_fails(mock_get):
    mock_get.return_value = None
    assert IndeedScraper().search(["python"]) == []
```

Create `tests/test_scraper_bing.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_indeed.py tests/test_scraper_bing.py -v`
Expected: FAIL — 2x `ModuleNotFoundError`

- [ ] **Step 3: Implement `scrapers/indeed.py`**

```python
import logging

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, JobListing
from scrapers.http_utils import get_with_retry

logger = logging.getLogger(__name__)


class IndeedScraper(BaseScraper):
    name = "Indeed"
    SEARCH_URL = "https://tr.indeed.com/jobs"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        if not keywords:
            return []
        params = {"q": keywords[0], "l": "Türkiye"}
        resp = get_with_retry(self.SEARCH_URL, params=params, timeout=self.TIMEOUT)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_="job_seen_beacon") or soup.find_all("td", class_="resultContent")
        results = []
        for card in cards[:30]:
            title_el = card.find("h2", class_="jobTitle") or card.find("a", {"data-jk": True})
            if not title_el:
                continue
            title = title_el.get_text(strip=True).replace("new", "").strip()

            link_el = card.find("a", href=True)
            if not link_el:
                continue
            href = link_el.get("href", "")
            url = f"https://tr.indeed.com{href}" if href.startswith("/") else href
            if "indeed.com" not in url:
                continue

            company_el = card.find("span", {"data-testid": "company-name"}) or card.find("span", class_="companyName")
            company = company_el.get_text(strip=True) if company_el else "Indeed İlanı"

            location_el = card.find("div", {"data-testid": "text-location"}) or card.find("div", class_="companyLocation")
            location = location_el.get_text(strip=True) if location_el else ""

            results.append(JobListing(title=title, company=company, url=url, source=self.name, location=location))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 4: Implement `scrapers/bing.py`**

```python
import logging

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, JobListing
from scrapers.http_utils import get_with_retry

logger = logging.getLogger(__name__)


class BingScraper(BaseScraper):
    name = "Bing"
    SEARCH_URL = "https://www.bing.com/search"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        if not keywords:
            return []
        query = f"{keywords[0]} job turkey site:linkedin.com OR site:indeed.com"
        resp = get_with_retry(self.SEARCH_URL, params={"q": query}, timeout=self.TIMEOUT)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for result in soup.find_all("li", class_="b_algo")[:20]:
            a_tag = result.find("a", href=True)
            if not a_tag:
                continue
            url = a_tag.get("href", "")
            title = a_tag.get_text(strip=True)
            if "linkedin" in url:
                source = "LinkedIn (Bing)"
            elif "indeed" in url:
                source = "Indeed (Bing)"
            else:
                continue

            results.append(JobListing(title=title, company="Bing Search", url=url, source=source))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_indeed.py tests/test_scraper_bing.py -v`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/indeed.py scrapers/bing.py tests/test_scraper_indeed.py tests/test_scraper_bing.py
git commit -m "feat: add hardened Indeed and Bing scrapers"
```

---

### Task 9: DuckDuckGo discovery fallback (Kariyer.net, SecretCV.com, and other ATS sites)

Ports `functions.py:internette_is_ara()`'s DuckDuckGo section (lines 452-527 on `main`) into its own module. This is the **documented fallback**, not a real scraper, for the two sites verified un-scrapable directly: Kariyer.net (PerimeterX/CAPTCHA) and SecretCV.com (listing links are JS-only / login-gated, see spec section "Doğrulanan teknik bulgular").

**Files:**
- Create: `scrapers/ddg_fallback.py`
- Test: `tests/test_scraper_ddg_fallback.py`

**Interfaces:**
- Consumes: `scrapers.base.JobListing`/`BaseScraper` (Task 1).
- Produces: `DdgFallbackScraper` class, `name = "DDG Discovery"`. Per-result `source` field is set dynamically per matched domain (`"Kariyer.net"`, `"SecretCV"`, `"Glassdoor"`, etc.) same as today's behavior.

- [ ] **Step 1: Write the failing test**

Create `tests/test_scraper_ddg_fallback.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_ddg_fallback.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.ddg_fallback'`

- [ ] **Step 3: Implement `scrapers/ddg_fallback.py`**

```python
import logging
import time

from duckduckgo_search import DDGS

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)

DOMAIN_LABELS = {
    "kariyer.net": "Kariyer.net",
    "yenibiris": "Yenibiris",
    "secretcv": "SecretCV",
    "eleman.net": "Eleman.net",
    "glassdoor": "Glassdoor",
    "greenhouse": "Greenhouse",
    "lever.co": "Lever",
    "indeed": "Indeed",
    "startupjobs": "StartupJobs",
    "wellfound": "Wellfound",
    "workable": "Workable",
}

SITE_QUERIES = [
    'site:kariyer.net "{q}" iş ilanı',
    'site:secretcv.com "{q}"',
    'site:glassdoor.com "{q}" turkey OR türkiye',
    'site:boards.greenhouse.io "{q}"',
    'site:jobs.lever.co "{q}"',
    'site:wellfound.com "{q}"',
]


class DdgFallbackScraper(BaseScraper):
    """Kariyer.net ve SecretCV.com PerimeterX/login korumaları nedeniyle
    dogrudan scrape edilemiyor (bkz. docs/superpowers/specs/2026-07-02-modular-scraping-engine-design.md).
    Bu scraper, DuckDuckGo site: aramasiyla dolayli sonuc bulur; kapsam ve
    dogruluk gercek bir scraper kadar guvenilir degildir."""

    name = "DDG Discovery"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        if not keywords:
            return []
        query_term = keywords[0]
        results = []
        try:
            with DDGS() as ddgs:
                for query_template in SITE_QUERIES:
                    time.sleep(0.8)
                    query = query_template.format(q=query_term)
                    try:
                        hits = ddgs.text(query, region="tr-tr", max_results=10, backend="lite")
                    except Exception as e:
                        logger.debug(f"DDGS sorgu hatasi ({query[:30]}...): {e}")
                        continue

                    for hit in hits or []:
                        link = hit.get("href", "")
                        title = hit.get("title", "")
                        body = hit.get("body", "")
                        if not link.startswith("http"):
                            continue

                        source = next((label for domain, label in DOMAIN_LABELS.items() if domain in link), "Web")
                        company = "İş İlanı"
                        for sep in [" - ", " | ", " — ", " at ", " · "]:
                            if sep in title:
                                parts = title.split(sep)
                                title = parts[0].strip()
                                if len(parts) > 1:
                                    company = parts[1].strip()
                                break

                        results.append(JobListing(
                            title=title[:100],
                            company=company[:50],
                            url=link,
                            source=source,
                            description=body[:150],
                        ))
                        if len(results) >= limit:
                            return results
        except Exception as e:
            logger.warning(f"DDG fallback hatasi: {e}")
            return []
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_ddg_fallback.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/ddg_fallback.py tests/test_scraper_ddg_fallback.py
git commit -m "feat: add DuckDuckGo discovery fallback for Kariyer.net/SecretCV.com"
```

---

### Task 10: Jooble scraper (optional, API-key gated)

Jooble is free but requires a per-developer API key (register at jooble.org/api/about). The scraper must no-op cleanly when no key is configured, so the app works without it.

**Files:**
- Create: `scrapers/jooble.py`
- Test: `tests/test_scraper_jooble.py`
- Modify: `.env.example` — add `JOOBLE_API_KEY=` line with a comment

**Interfaces:**
- Produces: `JoobleScraper` class, `name = "Jooble"`. Reads `JOOBLE_API_KEY` from environment at call time (not import time, so tests can monkeypatch it). `search()` returns `[]` immediately if the key is unset.

- [ ] **Step 1: Write the failing test**

Create `tests/test_scraper_jooble.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_jooble.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.jooble'`

- [ ] **Step 3: Implement `scrapers/jooble.py`**

```python
import logging
import os

import requests

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class JoobleScraper(BaseScraper):
    name = "Jooble"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        api_key = os.getenv("JOOBLE_API_KEY")
        if not api_key or not keywords:
            return []

        url = f"https://jooble.org/api/{api_key}"
        payload = {"keywords": keywords[0], "location": "Turkey"}
        try:
            resp = requests.post(url, json=payload, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"Jooble istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            logger.warning(f"Jooble beklenmeyen durum kodu: {resp.status_code}")
            return []

        results = []
        for job in resp.json().get("jobs", []):
            results.append(JobListing(
                title=job.get("title", ""),
                company=job.get("company", "Jooble İlanı"),
                url=job.get("link", ""),
                source=self.name,
                location=job.get("location", ""),
                description=job.get("snippet", "")[:200],
            ))
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 4: Add `JOOBLE_API_KEY` to `.env.example`**

In `.env.example`, after the `SECRET_KEY` line, add:

```
# Jooble API Anahtari (opsiyonel - https://jooble.org/api/about adresinden ucretsiz alinir)
# Bos birakilirsa Jooble kaynagi devre disi kalir, uygulama sorunsuz calisir
JOOBLE_API_KEY=
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_scraper_jooble.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/jooble.py tests/test_scraper_jooble.py .env.example
git commit -m "feat: add optional Jooble scraper (API-key gated)"
```

---

### Task 11: Scraper registry

**Files:**
- Create: `scrapers/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: every scraper class from Tasks 2-10.
- Produces: `scrapers.registry.get_active_scrapers() -> list[BaseScraper]`. Always includes all always-on scrapers; includes `JoobleScraper` only if `JOOBLE_API_KEY` is set (checked at call time, so tests can toggle it).

- [ ] **Step 1: Write the failing test**

Create `tests/test_registry.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.registry'`

- [ ] **Step 3: Implement `scrapers/registry.py`**

```python
import os

from scrapers.arbeitnow import ArbeitnowScraper
from scrapers.base import BaseScraper
from scrapers.bing import BingScraper
from scrapers.ddg_fallback import DdgFallbackScraper
from scrapers.eleman import ElemanScraper
from scrapers.findwork import FindWorkScraper
from scrapers.himalayas import HimalayasScraper
from scrapers.indeed import IndeedScraper
from scrapers.jooble import JoobleScraper
from scrapers.linkedin import LinkedinScraper
from scrapers.remoteok import RemoteOkScraper
from scrapers.remotive import RemotiveScraper
from scrapers.weworkremotely import WeWorkRemotelyScraper
from scrapers.yenibiris import YenibirisScraper

ALWAYS_ON_SCRAPERS = [
    LinkedinScraper,
    IndeedScraper,
    BingScraper,
    ArbeitnowScraper,
    RemotiveScraper,
    HimalayasScraper,
    FindWorkScraper,
    RemoteOkScraper,
    WeWorkRemotelyScraper,
    YenibirisScraper,
    ElemanScraper,
    DdgFallbackScraper,
]


def get_active_scrapers() -> list[BaseScraper]:
    scrapers = [cls() for cls in ALWAYS_ON_SCRAPERS]
    if os.getenv("JOOBLE_API_KEY"):
        scrapers.append(JoobleScraper())
    return scrapers
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_registry.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add scrapers/registry.py tests/test_registry.py
git commit -m "feat: add scraper registry"
```

---

### Task 12: Parallel orchestration service (`job_search_service.py`)

This is the task that delivers the actual speed win: today's sequential loop becomes a `ThreadPoolExecutor` fan-out with per-scraper timeout and centralized dedup.

**Files:**
- Create: `job_search_service.py` (repo root, alongside `app.py`/`functions.py`, matching existing flat layout)
- Test: `tests/test_job_search_service.py`

**Interfaces:**
- Consumes: `scrapers.registry.get_active_scrapers` (Task 11), `scrapers.base.JobListing` (Task 1).
- Produces: `job_search_service.search_jobs(keywords: list[str], per_source_limit: int = 20) -> list[dict]`. Each dict has keys `baslik, link, sirket, kaynak, aciklama` — this exact shape matches what `app.py:is_ara_sayfasi()` (Task 13) already expects from `functions.internette_is_ara`, so `app.py` only needs a one-line call-site swap, not a data-shape rewrite.

- [ ] **Step 1: Write the failing test**

Create `tests/test_job_search_service.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_job_search_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_search_service'`

- [ ] **Step 3: Implement `job_search_service.py`**

```python
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from scrapers.registry import get_active_scrapers

logger = logging.getLogger(__name__)

PER_SCRAPER_TIMEOUT = 12


def _extract_keywords(yetenekler_listesi: list[str]) -> list[str]:
    if not yetenekler_listesi:
        return ["Yazılım"]
    ana_yetenekler = []
    for yetenek in yetenekler_listesi[:3]:
        temiz = re.sub(r"\s*\(.*?\)", "", yetenek).strip()
        if len(temiz) >= 2:
            ana_yetenekler.append(temiz)
    return ana_yetenekler or ["Developer"]


def _run_scraper(scraper, keywords, per_source_limit):
    try:
        return scraper.search(keywords, limit=per_source_limit)
    except Exception as e:
        logger.warning(f"{scraper.name} scraper hatasi: {e}")
        return []


def search_jobs(yetenekler_listesi: list[str], per_source_limit: int = 20) -> list[dict]:
    keywords = _extract_keywords(yetenekler_listesi)
    scrapers = get_active_scrapers()

    all_listings = []
    with ThreadPoolExecutor(max_workers=len(scrapers) or 1) as executor:
        futures = {executor.submit(_run_scraper, s, keywords, per_source_limit): s for s in scrapers}
        for future in as_completed(futures):
            scraper = futures[future]
            try:
                listings = future.result(timeout=PER_SCRAPER_TIMEOUT)
            except Exception as e:
                logger.warning(f"{scraper.name} zaman asimina ugradi veya hata verdi: {e}")
                continue
            all_listings.extend(listings)

    seen_keys = set()
    deduped = []
    for listing in all_listings:
        key = listing.dedupe_key()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(listing)

    kaynak_sayilari = {}
    for listing in deduped:
        kaynak_sayilari[listing.source] = kaynak_sayilari.get(listing.source, 0) + 1
    logger.info(f"Toplam {len(deduped)} ilan bulundu. Kaynak dagilimi: {kaynak_sayilari}")

    return [
        {
            "baslik": listing.title,
            "link": listing.url,
            "sirket": listing.company,
            "kaynak": listing.source,
            "aciklama": listing.location or listing.description,
        }
        for listing in deduped
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_job_search_service.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add job_search_service.py tests/test_job_search_service.py
git commit -m "feat: add parallel job_search_service orchestrator"
```

---

### Task 13: Wire `job_search_service` into `app.py`, update dependencies and README

**Files:**
- Modify: `app.py:1-13` (imports), `app.py:212-247` (`is_ara_sayfasi` route)
- Modify: `requirements.txt` — add `lxml`
- Modify: `README.md` — correct the source list and document the Kariyer.net/SecretCV.com limitation
- Create: `tests/conftest.py`
- Test: `tests/test_app_is_ara.py`

**Interfaces:**
- Consumes: `job_search_service.search_jobs` (Task 12).

- [ ] **Step 1: Write the failing integration test**

Create `tests/conftest.py`:

```python
import pytest

from app import app as flask_app
from extensions import db


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.app_context():
        db.create_all()
        yield flask_app.test_client()
        db.session.remove()
        db.drop_all()
```

Create `tests/test_app_is_ara.py`:

```python
from unittest.mock import patch

from app import app as flask_app
from extensions import db
import models


def _login_with_cv(client):
    with flask_app.app_context():
        user = models.Kullanici(email="test@example.com", parola="hashed")
        db.session.add(user)
        db.session.commit()
        cv = models.CV(orjinal_dosya_adi="test.pdf", aday_id=user.id, cikarilan_veriler={"yetenekler": ["Python"]})
        db.session.add(cv)
        db.session.commit()
        user_id, cv_id = user.id, cv.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    return cv_id


@patch("app.job_search_service.search_jobs")
def test_is_ara_creates_ilan_from_job_search_service(mock_search_jobs, client):
    mock_search_jobs.return_value = [
        {"baslik": "Python Developer", "link": "https://example.com/job/1", "sirket": "Acme", "kaynak": "Test", "aciklama": "Istanbul"},
    ]
    cv_id = _login_with_cv(client)

    resp = client.post("/is-ara", data={"secilen_cv_id": cv_id}, follow_redirects=True)

    assert resp.status_code == 200
    with flask_app.app_context():
        assert models.IsIlani.query.filter_by(kaynak_url="https://example.com/job/1").count() == 1
    mock_search_jobs.assert_called_once_with(["Python"])


@patch("app.job_search_service.search_jobs")
def test_is_ara_shows_warning_when_no_results(mock_search_jobs, client):
    mock_search_jobs.return_value = []
    cv_id = _login_with_cv(client)

    resp = client.post("/is-ara", data={"secilen_cv_id": cv_id}, follow_redirects=True)

    assert resp.status_code == 200
    assert "bulunamad".encode("utf-8") in resp.data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/test_app_is_ara.py -v`
Expected: FAIL — `AttributeError: module 'app' has no attribute 'job_search_service'` (or the route still calls `functions.internette_is_ara`, which isn't mocked, so the assertion on `IsIlani` count fails)

- [ ] **Step 3: Add the import**

In `app.py`, after the existing `import functions` line (line 11), add:

```python
import functions
from extensions import db
import models
import job_search_service
```

(replacing the existing 3-line import block that currently reads `import functions` / `from extensions import db` / `import models` — just add the `import job_search_service` line after it.)

- [ ] **Step 4: Replace the scraping call site**

In `app.py`, inside `is_ara_sayfasi()` (around line 218-245), replace:

```python
            try:
                sonuclar, err = functions.internette_is_ara(cv.cikarilan_veriler.get('yetenekler', []))
                if sonuclar:
```

with:

```python
            try:
                sonuclar = job_search_service.search_jobs(cv.cikarilan_veriler.get('yetenekler', []))
                if sonuclar:
```

Everything below the `if sonuclar:` line (the `for ilan in sonuclar:` loop, the `else: flash(...)`, and the `except Exception as e:` block) stays exactly as-is — `job_search_service.search_jobs` returns the same `list[dict]` shape with the same keys (`baslik, link, sirket, kaynak, aciklama`) that the loop already consumes.

- [ ] **Step 5: Add `lxml` to `requirements.txt`**

In `requirements.txt`, under the `# HTTP & Web Scraping` section, add a line after `beautifulsoup4>=4.12.0`:

```
lxml>=4.9.0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine" && python -m pytest tests/ -v`
Expected: all tests across the whole suite pass (this also re-runs every scraper test from Tasks 1-12 as a full regression check).

- [ ] **Step 7: Update README.md source list and document the Kariyer.net/SecretCV.com limitation**

In `README.md`, replace the line:

```
- **Distributed Meta-Search Engine:** Implements a concurrent search architecture using `ThreadPoolExecutor` to scrape and aggregate job listings from LinkedIn, Indeed, and local sources via DuckDuckGo and specialized scrapers.[cite: 6, 10]
```

with:

```
- **Distributed Meta-Search Engine:** A modular `scrapers/` package (one file per source) runs concurrently via `ThreadPoolExecutor` with per-source timeouts, aggregating LinkedIn, Indeed, Bing, Arbeitnow, Remotive, Himalayas, FindWork.dev, RemoteOK, WeWorkRemotely, Yenibiris.com, Eleman.net, and (optionally, with a free API key) Jooble. Kariyer.net (PerimeterX bot protection) and SecretCV.com (login-gated listing pages) cannot be scraped directly and fall back to DuckDuckGo `site:` discovery, which is lower-coverage and clearly labeled as such in the code (`scrapers/ddg_fallback.py`).
```

- [ ] **Step 8: Commit**

```bash
cd "C:\Users\Monster\Desktop\AI-Career-Assistant-Engine"
git add app.py requirements.txt README.md tests/conftest.py tests/test_app_is_ara.py
git commit -m "feat: wire job_search_service into is-ara route, update deps and README"
```
