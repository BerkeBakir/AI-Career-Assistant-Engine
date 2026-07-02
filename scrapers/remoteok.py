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
