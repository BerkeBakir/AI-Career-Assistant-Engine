from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class JobListing:
    title: str
    company: str
    url: str
    source: str
    description: str = ""
    location: str = ""

    def dedupe_key(self) -> str:
        parsed = urlparse(self.url)
        path = parsed.path.rstrip('/')
        return f"{parsed.netloc.lower()}{path}"


class BaseScraper(ABC):
    name: str = "BaseScraper"

    @abstractmethod
    def search(self, keywords: list[str], limit: int = 20) -> list[JobListing]:
        raise NotImplementedError
