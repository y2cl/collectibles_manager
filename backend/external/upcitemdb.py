"""
UPCitemdb API client for barcode-based product lookup.
Trial endpoint works without a key (100 req/day).
Register at upcitemdb.com for a free key with higher limits.
"""
import logging
from typing import Optional, Dict

import requests

logger = logging.getLogger(__name__)

TRIAL_URL = "https://api.upcitemdb.com/prod/trial/lookup"
PAID_URL  = "https://api.upcitemdb.com/prod/v1/lookup"


def lookup_upc(upc: str, api_key: str = "") -> Optional[Dict]:
    """
    Look up a product by UPC/EAN barcode.
    Returns a normalized dict on success, None on miss or error.
    """
    url = PAID_URL if api_key else TRIAL_URL
    headers = {"user_key": api_key} if api_key else {}

    try:
        response = requests.get(url, params={"upc": upc}, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            logger.info("UPCitemdb: no results for UPC %s", upc)
            return None

        item = items[0]

        # Pull the best available price from store listings
        stores = item.get("offers", [])
        price = None
        for store in stores:
            try:
                price = float(store.get("price") or 0) or None
                if price:
                    break
            except (TypeError, ValueError):
                continue

        images = item.get("images", [])

        return {
            "name":         item.get("title", ""),
            "manufacturer": item.get("brand", ""),
            "description":  item.get("description", ""),
            "image_url":    images[0] if images else "",
            "price":        price,
            "upc":          upc,
            "category":     item.get("category", ""),
        }

    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            logger.warning("UPCitemdb: daily rate limit reached (100 req/day on trial)")
        else:
            logger.error("UPCitemdb HTTP error: %s", e)
        return None
    except Exception as e:
        logger.error("UPCitemdb lookup error: %s", e)
        return None
