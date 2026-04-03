"""
SerpAPI — Google Images search.
Free tier: 250 searches/month.

Setup (one-time, ~2 minutes):
  1. Sign up at https://serpapi.com (free, no credit card required)
  2. Go to Dashboard → copy your API key
  3. Add to backend/.env:
       SERPAPI_KEY=your_key_here
"""
import logging
from typing import List, Dict

import requests

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"


def search_images(query: str, api_key: str, num: int = 10) -> List[Dict]:
    """
    Search Google Images via SerpAPI.
    Returns a list of {url, thumbnail, title, source} dicts.
    Returns an empty list (not an error) when no results are found.
    Raises ValueError if API credentials are not configured.
    """
    if not api_key:
        raise ValueError("SerpAPI key is not configured.")

    params = {
        "engine":  "google_images",
        "q":       query,
        "api_key": api_key,
        "num":     min(num, 10),
        "safe":    "active",
    }

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("images_results", [])[:num]:
            results.append({
                "url":       item.get("original", ""),
                "thumbnail": item.get("thumbnail", item.get("original", "")),
                "title":     item.get("title", ""),
                "source":    item.get("source", ""),
            })
        return results

    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        body = ""
        if e.response is not None:
            try:
                body = e.response.json().get("error", e.response.text[:300])
            except Exception:
                body = e.response.text[:300]
        logger.error("SerpAPI HTTP %s: %s", status, body)
        raise RuntimeError(f"SerpAPI returned {status}: {body}") from e
    except Exception as e:
        logger.error("SerpAPI search error: %s", e)
        raise
