import os

from scrapers.arbeitnow import ArbeitnowScraper
from scrapers.base import BaseScraper
from scrapers.bing import BingScraper
from scrapers.ddg_fallback import DdgFallbackScraper
from scrapers.eleman import ElemanScraper
from scrapers.findwork import FindWorkScraper
from scrapers.himalayas import HimalayasScraper
from scrapers.indeed import IndeedScraper
from scrapers.jooble import JoobleScraper
from scrapers.linkedin import LinkedinScraper
from scrapers.remoteok import RemoteOkScraper
from scrapers.remotive import RemotiveScraper
from scrapers.weworkremotely import WeWorkRemotelyScraper
from scrapers.yenibiris import YenibirisScraper

ALWAYS_ON_SCRAPERS = [
    LinkedinScraper,
    IndeedScraper,
    BingScraper,
    ArbeitnowScraper,
    RemotiveScraper,
    HimalayasScraper,
    FindWorkScraper,
    RemoteOkScraper,
    WeWorkRemotelyScraper,
    YenibirisScraper,
    ElemanScraper,
    DdgFallbackScraper,
]


def get_active_scrapers() -> list[BaseScraper]:
    scrapers = [cls() for cls in ALWAYS_ON_SCRAPERS]
    if os.getenv("JOOBLE_API_KEY"):
        scrapers.append(JoobleScraper())
    return scrapers
