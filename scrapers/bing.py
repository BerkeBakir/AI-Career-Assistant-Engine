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
