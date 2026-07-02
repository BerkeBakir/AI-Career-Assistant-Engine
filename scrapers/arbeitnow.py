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
