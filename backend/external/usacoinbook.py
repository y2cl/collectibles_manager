"""
USA Coin Book scraper — fallback data source for coin lookups.

Used when NGC Price Guide is unavailable or returns no results.

Strategy: construct the coin page URL directly from the coin name
(e.g. "Morgan Dollar" → https://www.usacoinbook.com/coins/morgan-dollar/)
rather than scraping an index page. Individual coin pages have static
HTML grade/price tables that BeautifulSoup can parse.
"""
import re
import hashlib
import logging
from typing import List, Dict, Tuple, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

UCB_BASE = "https://www.usacoinbook.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.usacoinbook.com/",
}

_MID_GRADE_PRIORITY = ["MS-63", "MS-64", "VF-20", "VF-30", "F-12", "EF-40", "AU-50",
                        "Fine", "Very Fine", "Unc."]

# Hardcoded slug overrides for names whose slug can't be derived automatically
_SLUG_OVERRIDES: Dict[str, str] = {
    "morgan dollar":         "morgan-dollar",
    "morgan":                "morgan-dollar",
    "peace dollar":          "peace-dollar",
    "lincoln cent":          "lincoln-cent",
    "wheat cent":            "wheat-cent",
    "wheat penny":           "wheat-cent",
    "indian cent":           "indian-head-cent",
    "indian head cent":      "indian-head-cent",
    "buffalo nickel":        "buffalo-nickel",
    "jefferson nickel":      "jefferson-nickel",
    "liberty nickel":        "liberty-nickel",
    "mercury dime":          "mercury-dime",
    "roosevelt dime":        "roosevelt-dime",
    "barber dime":           "barber-dime",
    "barber quarter":        "barber-quarter",
    "standing liberty":      "standing-liberty-quarter",
    "washington quarter":    "washington-quarter",
    "walking liberty":       "walking-liberty-half-dollar",
    "franklin half":         "franklin-half-dollar",
    "kennedy half":          "kennedy-half-dollar",
    "barber half":           "barber-half-dollar",
    "eisenhower dollar":     "eisenhower-dollar",
    "ike dollar":            "eisenhower-dollar",
    "susan b anthony":       "susan-b-anthony-dollar",
    "sacagawea":             "sacagawea-dollar",
    "trade dollar":          "trade-dollar",
    "saint gaudens":         "saint-gaudens-double-eagle",
    "silver eagle":          "american-silver-eagle",
    "gold eagle":            "american-gold-eagle",
    "american silver eagle": "american-silver-eagle",
    "american gold eagle":   "american-gold-eagle",
}


def _name_to_slug(name: str) -> str:
    """Convert 'Morgan Dollar' → 'morgan-dollar'."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-")


def _candidate_urls(coin_name: str) -> List[Tuple[str, str]]:
    """
    Generate candidate (label, url) pairs to try for a coin name.
    Tries the slug override map first, then automatic slug derivation.
    """
    name_lower = coin_name.lower().strip()
    candidates: List[Tuple[str, str]] = []
    seen: set = set()

    def _add(slug: str, label: str) -> None:
        url = f"{UCB_BASE}/coins/{slug}/"
        if url not in seen:
            seen.add(url)
            candidates.append((label, url))

    # 1. Check override map
    for key, slug in _SLUG_OVERRIDES.items():
        if key in name_lower or name_lower in key:
            _add(slug, coin_name)

    # 2. Auto-derived slug from the full name
    auto_slug = _name_to_slug(coin_name)
    if auto_slug:
        _add(auto_slug, coin_name)
        # Also try with common suffixes stripped / altered
        for suffix in ["-dollar", "-cent", "-dime", "-nickel", "-quarter", "-half"]:
            if auto_slug.endswith(suffix):
                _add(auto_slug + "s", coin_name)   # pluralised
                break

    return candidates[:4]


def _coin_id(series: str, year: str, mint: str) -> str:
    key = f"ucb-{series.lower().strip()}-{year.strip()}-{mint.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _to_price(text: str) -> Optional[float]:
    cleaned = re.sub(r"[^0-9.]", "", text.replace(",", ""))
    if not cleaned:
        return None
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def _fetch(url: str, timeout: int = 20) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        logger.debug("UCB fetch OK: %s (%d bytes)", url, len(resp.content))
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.warning("USA Coin Book fetch error for %s: %s", url, e)
        raise


def _parse_coin_page(
    soup: BeautifulSoup,
    series_name: str,
    year_filter: str,
    mint_filter: str,
    series_url: str,
) -> List[Dict]:
    """Parse a USA Coin Book coin series page for grade/price data."""
    tables = soup.find_all("table")
    coins: List[Dict] = []

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [h.get_text(strip=True) for h in header_cells]

        grade_cols: Dict[int, str] = {}
        for i, h in enumerate(headers):
            if re.match(r"^(AG|G|VG|F|VF|EF|XF|AU|MS|PR|PF|BU)-\d+$", h):
                grade_cols[i] = h
            elif h in {"Good", "Fine", "Very Fine", "Extremely Fine", "Unc.", "BU", "Proof"}:
                grade_cols[i] = h

        if not grade_cols:
            continue

        year_col = 0
        for i, h in enumerate(headers):
            if h.lower() in {"year", "date", "coin", "date & mint mark"}:
                year_col = i
                break

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells or len(cells) <= max(grade_cols.keys(), default=0):
                continue

            year_text = cells[year_col].get_text(strip=True) if year_col < len(cells) else ""
            if not year_text:
                continue

            year_match = re.search(r"(\d{4})", year_text)
            extracted_year = year_match.group(1) if year_match else ""

            mint_match = re.search(r"\d{4}[-\s]([A-Z]{1,2})\b", year_text)
            extracted_mint = mint_match.group(1).upper() if mint_match else ""

            if year_filter and extracted_year and extracted_year != year_filter.strip():
                continue
            if mint_filter and extracted_mint.upper() != mint_filter.upper().strip():
                continue

            prices_map: Dict[str, float] = {}
            for col_idx, grade_label in grade_cols.items():
                if col_idx < len(cells):
                    price = _to_price(cells[col_idx].get_text(strip=True))
                    if price is not None:
                        prices_map[grade_label] = price

            if not prices_map:
                continue

            prices_vals = list(prices_map.values())
            price_low = min(prices_vals)
            price_market = max(prices_vals)

            price_usd: float = 0.0
            for grade in _MID_GRADE_PRIORITY:
                if grade in prices_map:
                    price_usd = prices_map[grade]
                    break
            if price_usd == 0.0:
                price_usd = sorted(prices_vals)[len(prices_vals) // 2]

            coins.append({
                "id": _coin_id(series_name, extracted_year, extracted_mint),
                "game": "Coins",
                "name": series_name,
                "set": series_name,
                "set_code": "",
                "year": extracted_year,
                "card_number": year_text.strip(),
                "image_url": "",
                "image_url_back": "",
                "link": series_url,
                "price_usd": price_usd,
                "price_usd_foil": 0.0,
                "price_usd_etched": 0.0,
                "price_low": price_low,
                "price_mid": None,
                "price_market": price_market,
                "prices_map": prices_map,
                "has_nonfoil": False,
                "has_foil": False,
                "source": "USA Coin Book",
                "artist": "",
                "variant": "",
                "quantity": 1,
            })

    return coins


def search_usacoinbook(
    coin_name: str,
    year: str = "",
    mint_mark: str = "",
) -> Tuple[List[Dict], int, int, str]:
    """
    Search USA Coin Book for coins matching coin_name.
    Constructs direct coin page URLs from the name rather than scraping
    an index, so it works even if the index page returns 404.

    Returns (coins, shown, total, source_label).
    """
    candidates = _candidate_urls(coin_name)
    if not candidates:
        logger.info("USA Coin Book: no candidate URLs for %r", coin_name)
        return [], 0, 0, "USA Coin Book"

    all_coins: List[Dict] = []
    for series_name, series_url in candidates:
        try:
            soup = _fetch(series_url)
            if not soup:
                continue
            coins = _parse_coin_page(soup, series_name, year, mint_mark, series_url)
            if coins:
                all_coins.extend(coins)
                logger.debug("USA Coin Book: %d coins from %s", len(coins), series_url)
                break  # found a working page, stop trying other candidates
            else:
                logger.debug(
                    "USA Coin Book: page fetched but no table parsed at %s", series_url
                )
        except Exception as e:
            logger.debug("USA Coin Book: %s failed (%s), trying next candidate", series_url, e)
            continue

    return all_coins, len(all_coins), len(all_coins), "USA Coin Book"
