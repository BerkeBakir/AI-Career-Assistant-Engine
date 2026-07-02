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
