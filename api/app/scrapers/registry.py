from __future__ import annotations

from typing import Dict, Type

from app.scrapers.base import Scraper
from app.scrapers.countdown_api import CountdownAPIScraper
from app.scrapers.new_world_api import NewWorldAPIScraper
from app.scrapers.paknsave_api import PakNSaveAPIScraper

CHAINS: Dict[str, Type[Scraper]] = {
    "countdown": CountdownAPIScraper,
    "new_world": NewWorldAPIScraper,
    "paknsave": PakNSaveAPIScraper,
}


def get_chain_scraper(chain: str) -> Scraper:
    scraper_cls = CHAINS.get(chain)
    if not scraper_cls:
        raise ValueError(f"Unknown chain: {chain}")
    return scraper_cls()


__all__ = ["get_chain_scraper", "CHAINS"]
