"""
eBay Finding Service API client for sports card search.
Extracted from collectiman.py::baseball_search_ebay — all st.* calls removed.
"""
import logging
from typing import List, Dict, Tuple

import requests

logger = logging.getLogger(__name__)

EBAY_PROD_URL = "https://svcs.ebay.com/services/search/FindingService/v1"
EBAY_SBX_URL = "https://svcs.sandbox.ebay.com/services/search/FindingService/v1"

# eBay category IDs for sports trading cards
EBAY_SPORT_CATEGORIES = {
    "baseball": "212",
    "football": "214",
    "basketball": "217",
    "hockey": "216",
    "soccer": "218",
    "other": "219",
}


def _create_mock_cards(player_name: str, year: str, team: str,
                       set_name: str, card_number: str, sport: str = "baseball",
                       source: str = "Mock") -> List[Dict]:
    """Return a small set of mock sports cards when the real API is unavailable."""
    return [
        {
            "name": player_name or "Unknown Player",
            "set": set_name or "Unknown Set",
            "year": year or "",
            "team": team or "",
            "card_number": card_number or "",
            "position": "",
            "variety": "Base",
            "price_usd": 0.0,
            "image_url": "",
            "link": "",
            "game": "Sports Cards",
            "sport": sport,
            "quantity": 1,
            "variant": "",
            "source": source,
        }
        for _ in range(3)
    ]


def search_ebay_sports(
    player_name: str,
    year: str = "",
    team: str = "",
    set_name: str = "",
    card_number: str = "",
    sport: str = "baseball",
    ebay_app_id: str = "",
    ebay_env: str = "Sandbox",
) -> Tuple[List[Dict], int, int, str]:
    """
    Search eBay for sports cards using the Finding API.
    Returns (cards, shown_count, total_count, source_label).
    Falls back to mock data when credentials are missing or invalid.
    """
    category_id = EBAY_SPORT_CATEGORIES.get(sport.lower(), "219")

    if not ebay_app_id:
        logger.warning("eBay App ID not configured for %s environment", ebay_env)
        mock = _create_mock_cards(player_name, year, team, set_name, card_number, sport,
                                  f"eBay {ebay_env} (Mock - no key)")
        return mock, len(mock), len(mock), f"eBay {ebay_env} (Mock Data)"

    base_url = EBAY_PROD_URL if ebay_env == "Production" else EBAY_SBX_URL

    query_parts = [player_name.strip()]
    for part in [year, team, set_name]:
        if part:
            query_parts.append(part)
    if card_number:
        query_parts.append(f"#{card_number}")
    query = " ".join(query_parts) + f" {sport} card"

    params = {
        "OPERATION-NAME": "findItemsAdvanced",
        "SERVICE-VERSION": "1.0.0",
        "SECURITY-APPNAME": ebay_app_id,
        "RESPONSE-DATA-FORMAT": "JSON",
        "REST-PAYLOAD": "",
        "keywords": query,
        "categoryId": category_id,
        "itemFilter(0).name": "Condition",
        "itemFilter(0).value": "New",
        "itemFilter(1).name": "ListingType",
        "itemFilter(1).value": "AuctionWithBIN",
        "sortOrder": "BestMatch",
        "paginationInput.entriesPerPage": "50",
    }

    try:
        response = requests.get(base_url, params=params, timeout=30)

        if response.status_code in (401, 403):
            logger.warning("eBay authentication failed (%s)", ebay_env)
            mock = _create_mock_cards(player_name, year, team, set_name, card_number, sport,
                                      f"eBay {ebay_env} - Auth failed")
            return mock, len(mock), len(mock), f"eBay {ebay_env} (Mock Data)"

        response.raise_for_status()
        data = response.json()

        find_response = data.get("findItemsAdvancedResponse", [{}])[0]
        errors = find_response.get("errors", [])
        if errors and isinstance(errors, list):
            error_info = errors[0]
            error_id = error_info.get("errorId", [])
            message = error_info.get("message", [])
            if (isinstance(error_id, list) and "11002" in error_id) or (
                isinstance(message, list) and any("Invalid Application" in str(m) for m in message)
            ):
                mock = _create_mock_cards(player_name, year, team, set_name, card_number, sport,
                                          f"eBay {ebay_env} - App ID not registered")
                return mock, len(mock), len(mock), f"eBay {ebay_env} (Mock Data)"

        search_result = find_response.get("searchResult", [{}])[0].get("item", [])
        if not search_result:
            mock = _create_mock_cards(player_name, year, team, set_name, card_number, sport)
            return mock, len(mock), len(mock), f"eBay {ebay_env} (Mock Data)"

        cards: List[Dict] = []
        for item in search_result:
            try:
                card = {
                    "name": player_name,
                    "set": set_name or "Unknown Set",
                    "year": year or "",
                    "team": team or "",
                    "card_number": card_number or "",
                    "position": "",
                    "variety": "Base",
                    "price_usd": 0.0,
                    "image_url": item.get("galleryURL", [{}])[0] or "",
                    "link": item.get("viewItemURL", [{}])[0] or "",
                    "game": "Sports Cards",
                    "sport": sport,
                    "quantity": 1,
                    "variant": "",
                    "source": f"eBay {ebay_env}",
                }
                cards.append(card)
            except Exception:
                continue

        return cards, len(cards), len(cards), f"eBay {ebay_env}"

    except Exception as e:
        logger.error("eBay search error: %s", e)
        mock = _create_mock_cards(player_name, year, team, set_name, card_number, sport,
                                  f"eBay {ebay_env} Error")
        return mock, len(mock), len(mock), f"eBay {ebay_env} (Mock Data)"


# Backwards-compatible alias
def search_ebay_baseball(
    player_name: str,
    year: str = "",
    team: str = "",
    set_name: str = "",
    card_number: str = "",
    ebay_app_id: str = "",
    ebay_env: str = "Sandbox",
) -> Tuple[List[Dict], int, int, str]:
    return search_ebay_sports(
        player_name=player_name,
        year=year,
        team=team,
        set_name=set_name,
        card_number=card_number,
        sport="baseball",
        ebay_app_id=ebay_app_id,
        ebay_env=ebay_env,
    )
