import logging
import time

from duckduckgo_search import DDGS

from scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)

DOMAIN_LABELS = {
    "kariyer.net": "Kariyer.net",
    "yenibiris": "Yenibiris",
    "secretcv": "SecretCV",
    "eleman.net": "Eleman.net",
    "glassdoor": "Glassdoor",
    "greenhouse": "Greenhouse",
    "lever.co": "Lever",
    "indeed": "Indeed",
    "startupjobs": "StartupJobs",
    "wellfound": "Wellfound",
    "workable": "Workable",
}

SITE_QUERIES = [
    'site:kariyer.net "{q}" iş ilanı',
    'site:secretcv.com "{q}"',
    'site:glassdoor.com "{q}" turkey OR türkiye',
]


class DdgFallbackScraper(BaseScraper):
    """Kariyer.net ve SecretCV.com PerimeterX/login korumaları nedeniyle
    dogrudan scrape edilemiyor (bkz. docs/superpowers/specs/2026-07-02-modular-scraping-engine-design.md).
    Bu scraper, DuckDuckGo site: aramasiyla dolayli sonuc bulur; kapsam ve
    dogruluk gercek bir scraper kadar guvenilir degildir."""

    name = "DDG Discovery"
    TIMEOUT = 10

    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        if not keywords:
            return []
        query_term = keywords[0]
        results = []
        try:
            with DDGS() as ddgs:
                for query_template in SITE_QUERIES:
                    time.sleep(0.5)
                    query = query_template.format(q=query_term)
                    try:
                        hits = ddgs.text(query, region="tr-tr", max_results=10, backend="lite")
                    except Exception as e:
                        logger.debug(f"DDGS sorgu hatasi ({query[:30]}...): {e}")
                        continue

                    for hit in hits or []:
                        link = hit.get("href", "")
                        title = hit.get("title", "")
                        body = hit.get("body", "")
                        if not link.startswith("http"):
                            continue

                        source = next((label for domain, label in DOMAIN_LABELS.items() if domain in link), "Web")
                        company = "İş İlanı"
                        for sep in [" - ", " | ", " — ", " at ", " · "]:
                            if sep in title:
                                parts = title.split(sep)
                                title = parts[0].strip()
                                if len(parts) > 1:
                                    company = parts[1].strip()
                                break

                        results.append(JobListing(
                            title=title[:100],
                            company=company[:50],
                            url=link,
                            source=source,
                            description=body[:150],
                        ))
                        if len(results) >= limit:
                            return results
        except Exception as e:
            logger.warning(f"DDG fallback hatasi: {e}")
            return []
        return results
