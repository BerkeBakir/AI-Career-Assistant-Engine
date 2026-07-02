import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed

from scrapers.registry import get_active_scrapers

logger = logging.getLogger(__name__)

PER_SCRAPER_TIMEOUT = 12


def _extract_keywords(yetenekler_listesi: list[str]) -> list[str]:
    if not yetenekler_listesi:
        return ["Yazılım"]
    ana_yetenekler = []
    for yetenek in yetenekler_listesi[:3]:
        temiz = re.sub(r"\s*\(.*?\)", "", yetenek).strip()
        if len(temiz) >= 2:
            ana_yetenekler.append(temiz)
    return ana_yetenekler or ["Developer"]


def _run_scraper(scraper, keywords, per_source_limit):
    try:
        return scraper.search(keywords, limit=per_source_limit)
    except Exception as e:
        logger.warning(f"{scraper.name} scraper hatasi: {e}")
        return []


def search_jobs(yetenekler_listesi: list[str], per_source_limit: int = 20) -> list[dict]:
    keywords = _extract_keywords(yetenekler_listesi)
    scrapers = get_active_scrapers()

    all_listings = []
    executor = ThreadPoolExecutor(max_workers=len(scrapers) or 1)
    try:
        futures = {executor.submit(_run_scraper, s, keywords, per_source_limit): s for s in scrapers}
        try:
            # `timeout` here bounds the whole wait loop (wall-clock), not a single
            # future's `.result()` call. Passing timeout to `future.result()` instead
            # is a no-op: as_completed() only yields a future once it is already
            # done, so a per-future result(timeout=...) never has anything to wait
            # for and can't bound a hung/slow scraper's wall-clock time.
            for future in as_completed(futures, timeout=PER_SCRAPER_TIMEOUT):
                scraper = futures[future]
                try:
                    listings = future.result()
                except Exception as e:
                    logger.warning(f"{scraper.name} scraper hatasi: {e}")
                    continue
                all_listings.extend(listings)
        except FuturesTimeoutError:
            unfinished = [futures[f].name for f in futures if not f.done()]
            logger.warning(f"Zaman asimi: tamamlanmayan scraper'lar atlandi: {unfinished}")
    finally:
        # wait=False: don't block this call on stragglers that already missed the
        # timeout above. Their threads finish on their own; we just stop waiting.
        executor.shutdown(wait=False)

    seen_keys = set()
    deduped = []
    for listing in all_listings:
        key = listing.dedupe_key()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(listing)

    kaynak_sayilari = {}
    for listing in deduped:
        kaynak_sayilari[listing.source] = kaynak_sayilari.get(listing.source, 0) + 1
    logger.info(f"Toplam {len(deduped)} ilan bulundu. Kaynak dagilimi: {kaynak_sayilari}")

    return [
        {
            "baslik": listing.title,
            "link": listing.url,
            "sirket": listing.company,
            "kaynak": listing.source,
            "aciklama": listing.location or listing.description,
        }
        for listing in deduped
    ]
