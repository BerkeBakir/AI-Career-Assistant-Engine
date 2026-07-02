import logging
import random
import time

import requests

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def get_with_retry(url, params=None, headers=None, timeout=10, attempts=2):
    merged_headers = dict(headers or {})
    for attempt in range(1, attempts + 1):
        merged_headers["User-Agent"] = random.choice(USER_AGENTS)
        try:
            resp = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
        except requests.RequestException as e:
            logger.warning(f"HTTP istegi basarisiz (deneme {attempt}/{attempts}): {e}")
            if attempt < attempts:
                time.sleep(1)
            continue

        if resp.status_code < 500:
            return resp

        logger.warning(f"HTTP {resp.status_code} (deneme {attempt}/{attempts}): {url}")
        if attempt < attempts:
            time.sleep(1)

    return None
