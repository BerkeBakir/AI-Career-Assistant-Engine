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
                    location = " - ".join(parts[1:])

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
