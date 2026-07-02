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
