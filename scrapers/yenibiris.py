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
