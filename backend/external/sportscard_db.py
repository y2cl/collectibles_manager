"""
SportsCardDatabase.com search client.
Currently returns mock data (same as the original Streamlit implementation).
Replace with a real scraper when the site's structure is mapped out.
"""
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


def _create_mock_cards(player_name: str, year: str, set_name: str, card_number: str,
                       source: str = "SportsCardDatabase.com") -> List[Dict]:
    return [
        {
            "name": player_name or "Unknown Player",
            "set": set_name or "Unknown Set",
            "year": year or "",
            "team": "",
            "card_number": card_number or "",
            "position": "",
            "variety": "Base",
            "price_usd": 0.0,
            "image_url": "",
            "link": "",
            "game": "Baseball Cards",
            "quantity": 1,
            "variant": "",
            "source": source,
        }
        for _ in range(3)
    ]


def search_sportscard_database(
    player_name: str,
    year: str = "",
    set_name: str = "",
    card_number: str = "",
) -> Tuple[List[Dict], int, int, str]:
    """
    Search SportsCardDatabase.com.
    Returns (cards, shown_count, total_count, source_label).
    """
    logger.debug("SportsCardDatabase search: player=%s year=%s", player_name, year)
    cards = _create_mock_cards(player_name, year, set_name, card_number)
    return cards, len(cards), len(cards), "SportsCardDatabase.com"
