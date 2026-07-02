import logging

import requests

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class HimalayasScraper(BaseScraper):
    name = "Himalayas"
    API_URL = "https://himalayas.app/jobs/api?limit=30"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        try:
            resp = requests.get(self.API_URL, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"Himalayas istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            return []

        keywords_lower = [k.lower() for k in keywords]
        results = []
        for job in resp.json().get("jobs", []):
            title = job.get("title", "")
            if not any(k in title.lower() for k in keywords_lower):
                continue
            url = job.get("applicationLink") or f"https://himalayas.app/jobs/{job.get('slug', '')}"
            results.append(JobListing(
                title=title,
                company=job.get("companyName", "Himalayas"),
                url=url,
                source=self.name,
                location=f"Remote - {job.get('locationRestrictions', 'Worldwide')}",
            ))
            if len(results) >= limit:
                break
        return results
