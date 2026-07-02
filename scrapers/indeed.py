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
