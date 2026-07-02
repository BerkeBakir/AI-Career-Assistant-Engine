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
