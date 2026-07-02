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
