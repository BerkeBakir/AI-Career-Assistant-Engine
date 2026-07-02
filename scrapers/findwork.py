import logging

import requests

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class FindWorkScraper(BaseScraper):
    name = "FindWork.dev"
    API_URL = "https://findwork.dev/api/jobs/"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        try:
            resp = requests.get(self.API_URL, headers={"Accept": "application/json"}, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning(f"FindWork.dev istegi basarisiz: {e}")
            return []

        if resp.status_code != 200:
            return []

        keywords_lower = [k.lower() for k in keywords]
        results = []
        for job in resp.json().get("results", []):
            role = job.get("role", "")
            role_lower = role.lower()
            job_keywords = str(job.get("keywords", [])).lower()
            if not (any(k in role_lower for k in keywords_lower) or any(k in job_keywords for k in keywords_lower)):
                continue
            results.append(JobListing(
                title=role,
                company=job.get("company_name", "FindWork"),
                url=job.get("url", ""),
                source=self.name,
                location=job.get("location", "Remote"),
                description=", ".join(job.get("keywords", [])[:3]),
            ))
            if len(results) >= limit:
                break
        return results
