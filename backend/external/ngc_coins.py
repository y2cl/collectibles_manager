"""
NGC Coin Price Guide scraper — primary data source for coin lookups.

URL format:  https://www.ngccoin.com/price-guide/united-states/{category}/{id}/
  e.g. Morgan Dollars → dollars/49
       Lincoln Wheat  → dollars/99

Page structure
──────────────
The series page contains 3 HTML tables:
  Table 1 – a trivial 1-row navigation stub (ignored)
  Table 2 – the NGC Census table (one row per graded entry)
              First cell has `parent-coin-id` attribute → used to map coin-id → date label
  Table 3 – the Price Guide table (one row per date/variety)
              Row class: ['ms','1878'] or ['pf','2020'] — [strike_type, year]
              Cells with class 'base' carry: grade="{grade}" coin-id="{id}" and price text

Grade mapping
─────────────
Text grades returned as-is: PrAg, G, VG, F, VF, XF
Numeric grades:
  50–58  → AU-{n}
  60–70  → MS-{n}  for strike type 'ms' (and others)
           PF-{n}  for strike type 'pf'
"""
import re
import hashlib
import logging
from typing import List, Dict, Set, Tuple, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

NGC_BASE = "https://www.ngccoin.com"
NGC_PRICE_GUIDE = "https://www.ngccoin.com/price-guide/united-states"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.ngccoin.com/",
}

# ---------------------------------------------------------------------------
# Series map: keyword → list of (category, id, human_label) tuples.
# URL constructed as:  NGC_PRICE_GUIDE/{category}/{id}/
# Discovered by probing https://www.ngccoin.com/price-guide/united-states/{cat}/{id}/
# ---------------------------------------------------------------------------
NGC_SERIES_MAP: Dict[str, List[Tuple[str, int, str]]] = {
    # ── Half Cents ─────────────────────────────────────────────────────────
    "liberty cap half cent":  [("cents", 7, "Liberty Cap Half Cents (1793-1797)")],
    "draped bust half cent":  [("cents", 8, "Draped Bust Half Cents (1800-1808)")],
    "classic head half cent": [("cents", 9, "Classic Head Half Cents (1809-1836)")],
    "braided hair half cent":  [("cents", 10, "Braided Hair Half Cents (1840-1857)")],
    "half cent":               [("cents", 7,  "Liberty Cap Half Cents (1793-1797)"),
                                ("cents", 8,  "Draped Bust Half Cents (1800-1808)"),
                                ("cents", 9,  "Classic Head Half Cents (1809-1836)"),
                                ("cents", 10, "Braided Hair Half Cents (1840-1857)")],
    # ── Large / Early Cents ────────────────────────────────────────────────
    "chain cent":              [("cents", 11, "Chain and Wreath Cents (1793)")],
    "wreath cent":             [("cents", 11, "Chain and Wreath Cents (1793)")],
    "liberty cap cent":        [("cents", 12, "Liberty Cap Cents (1793-1796)")],
    "draped bust cent":        [("cents", 13, "Draped Bust Cents (1796-1807)")],
    "classic head cent":       [("cents", 14, "Classic Head Cents (1808-1814)")],
    "coronet cent":            [("cents", 15, "Coronet Head Cents (1816-1839)")],
    "matron head cent":        [("cents", 15, "Coronet Head Cents (1816-1839)")],
    "large cent":              [("cents", 11, "Chain and Wreath Cents (1793)"),
                                ("cents", 12, "Liberty Cap Cents (1793-1796)"),
                                ("cents", 13, "Draped Bust Cents (1796-1807)"),
                                ("cents", 14, "Classic Head Cents (1808-1814)"),
                                ("cents", 15, "Coronet Head Cents (1816-1839)")],
    # ── Small Cents ────────────────────────────────────────────────────────
    "flying eagle":            [("cents", 16, "Flying Eagle Cents (1856-1858)")],
    "flying eagle cent":       [("cents", 16, "Flying Eagle Cents (1856-1858)")],
    "indian cent":             [("cents", 17, "Indian Cents (1859-1909)")],
    "indian head cent":        [("cents", 17, "Indian Cents (1859-1909)")],
    "indian head penny":       [("cents", 17, "Indian Cents (1859-1909)")],
    "wheat cent":              [("dollars", 99, "Lincoln Cents, Wheat Reverse (1909-1958)")],
    "wheat penny":             [("dollars", 99, "Lincoln Cents, Wheat Reverse (1909-1958)")],
    "lincoln wheat":           [("dollars", 99, "Lincoln Cents, Wheat Reverse (1909-1958)")],
    "lincoln cent":            [("dollars", 99,  "Lincoln Cents, Wheat Reverse (1909-1958)"),
                                ("dollars", 100, "Lincoln Cents, Memorial Reverse (1959-2008)"),
                                ("dollars", 101, "Lincoln Cents, Bicentennial and Shield (2009-Date)")],
    "lincoln memorial cent":   [("dollars", 100, "Lincoln Cents, Memorial Reverse (1959-2008)")],
    "lincoln shield cent":     [("dollars", 101, "Lincoln Cents, Bicentennial and Shield (2009-Date)")],
    # ── Two Cents / Three Cents ────────────────────────────────────────────
    "two cent":                [("cents", 19, "Shield Two Cents (1864-1873)")],
    "2 cent":                  [("cents", 19, "Shield Two Cents (1864-1873)")],
    "silver three cent":       [("cents", 20, "Silver Three Cents (1851-1873)")],
    "nickel three cent":       [("cents", 21, "Nickel Three Cents (1865-1889)")],
    "three cent":              [("cents", 20, "Silver Three Cents (1851-1873)"),
                                ("cents", 21, "Nickel Three Cents (1865-1889)")],
    # ── Nickels ────────────────────────────────────────────────────────────
    "shield nickel":           [("cents", 22, "Shield Five Cents (1866-1883)")],
    "liberty nickel":          [("cents", 23, "Liberty Head Five Cents (1883-1913)")],
    "liberty head nickel":     [("cents", 23, "Liberty Head Five Cents (1883-1913)")],
    "v nickel":                [("cents", 23, "Liberty Head Five Cents (1883-1913)")],
    "buffalo nickel":          [("cents", 24, "Buffalo Five Cents (1913-1938)")],
    "indian head nickel":      [("cents", 24, "Buffalo Five Cents (1913-1938)")],
    "jefferson nickel":        [("cents", 25, "Jefferson Five Cents (1938-Date)")],
    "nickel":                  [("cents", 22, "Shield Five Cents (1866-1883)"),
                                ("cents", 23, "Liberty Head Five Cents (1883-1913)"),
                                ("cents", 24, "Buffalo Five Cents (1913-1938)"),
                                ("cents", 25, "Jefferson Five Cents (1938-Date)")],
    # ── Half Dimes ────────────────────────────────────────────────────────
    "early half dime":         [("cents", 26, "Early Half Dimes (1792-1837)")],
    "seated liberty half dime":[("cents", 27, "Seated Liberty Half Dimes (1837-1873)")],
    "half dime":               [("cents", 26, "Early Half Dimes (1792-1837)"),
                                ("cents", 27, "Seated Liberty Half Dimes (1837-1873)")],
    # ── Dimes ─────────────────────────────────────────────────────────────
    "early dime":              [("cents", 28, "Early Dimes (1796-1837)")],
    "seated liberty dime":     [("cents", 29, "Seated Liberty Dimes (1837-1891)")],
    "barber dime":             [("cents", 30, "Barber Dimes (1892-1916)")],
    "mercury dime":            [("cents", 31, "Mercury Dimes (1916-1945)")],
    "winged liberty dime":     [("cents", 31, "Mercury Dimes (1916-1945)")],
    "roosevelt dime":          [("cents", 32, "Roosevelt Dimes (1946-Date)")],
    "dime":                    [("cents", 29, "Seated Liberty Dimes (1837-1891)"),
                                ("cents", 30, "Barber Dimes (1892-1916)"),
                                ("cents", 31, "Mercury Dimes (1916-1945)"),
                                ("cents", 32, "Roosevelt Dimes (1946-Date)")],
    # ── Twenty Cents ─────────────────────────────────────────────────────
    "twenty cent":             [("cents", 33, "Twenty Cents (1875-1878)")],
    # ── Quarters ─────────────────────────────────────────────────────────
    "early quarter":           [("cents", 34, "Early Quarters (1796-1838)")],
    "seated liberty quarter":  [("cents", 35, "Seated Liberty Quarters (1838-1891)")],
    "barber quarter":          [("cents", 36, "Barber Quarters (1892-1916)")],
    "standing liberty quarter":[("cents", 37, "Standing Liberty Quarters (1916-1930)")],
    "standing liberty":        [("cents", 37, "Standing Liberty Quarters (1916-1930)")],
    "washington quarter":      [("cents", 38, "Washington Quarters (1932-1998)")],
    "state quarter":           [("dollars", 88, "State & Territorial Quarters (1999-2009)")],
    "territorial quarter":     [("dollars", 88, "State & Territorial Quarters (1999-2009)")],
    "atb quarter":             [("dollars", 103, "America the Beautiful Quarters (2010-2021)")],
    "america the beautiful":   [("dollars", 103, "America the Beautiful Quarters (2010-2021)")],
    "quarter":                 [("cents", 36, "Barber Quarters (1892-1916)"),
                                ("cents", 37, "Standing Liberty Quarters (1916-1930)"),
                                ("cents", 38, "Washington Quarters (1932-1998)"),
                                ("dollars", 88, "State & Territorial Quarters (1999-2009)")],
    # ── Half Dollars ─────────────────────────────────────────────────────
    "flowing hair half":       [("cents", 39, "Flowing Hair Half Dollars (1794-1795)")],
    "seated liberty half":     [("dollars", 40, "Seated Liberty Half Dollars (1839-1891)")],
    "barber half":             [("dollars", 41, "Barber Half Dollars (1892-1915)")],
    "barber half dollar":      [("dollars", 41, "Barber Half Dollars (1892-1915)")],
    "walking liberty":         [("dollars", 42, "Walking Liberty Half Dollars (1916-1947)")],
    "walking liberty half":    [("dollars", 42, "Walking Liberty Half Dollars (1916-1947)")],
    "franklin half":           [("dollars", 43, "Franklin Half Dollars (1948-1963)")],
    "franklin half dollar":    [("dollars", 43, "Franklin Half Dollars (1948-1963)")],
    "kennedy half":            [("dollars", 44, "Kennedy Half Dollars (1964-Date)")],
    "kennedy half dollar":     [("dollars", 44, "Kennedy Half Dollars (1964-Date)")],
    "half dollar":             [("dollars", 41, "Barber Half Dollars (1892-1915)"),
                                ("dollars", 42, "Walking Liberty Half Dollars (1916-1947)"),
                                ("dollars", 43, "Franklin Half Dollars (1948-1963)"),
                                ("dollars", 44, "Kennedy Half Dollars (1964-Date)")],
    # ── Silver Dollars ────────────────────────────────────────────────────
    "early dollar":            [("dollars", 45, "Early Dollars (1794-1804)")],
    "gobrecht dollar":         [("dollars", 46, "Gobrecht Dollars (1836-1839)")],
    "seated liberty dollar":   [("dollars", 47, "Seated Liberty Dollars (1840-1873)")],
    "trade dollar":            [("dollars", 48, "Trade Dollars (1873-1885)")],
    "morgan dollar":           [("dollars", 49, "Morgan Dollars (1878-1921)")],
    "morgan":                  [("dollars", 49, "Morgan Dollars (1878-1921)")],
    "peace dollar":            [("dollars", 50, "Peace Dollars (1921-1935)")],
    "eisenhower dollar":       [("dollars", 51, "Eisenhower Dollars (1971-1978)")],
    "ike dollar":              [("dollars", 51, "Eisenhower Dollars (1971-1978)")],
    "susan b anthony":         [("dollars", 52, "Anthony Dollars (1979-1999)")],
    "sba dollar":              [("dollars", 52, "Anthony Dollars (1979-1999)")],
    "sacagawea":               [("dollars", 53, "Sacagawea Dollars (2000-Date)")],
    "presidential dollar":     [("dollars", 89, "Presidential Dollars (2007-2020)")],
    # ── Gold Coins ────────────────────────────────────────────────────────
    "gold dollar":             [("dollars", 54, "Gold Dollars (1849-1889)")],
    "quarter eagle":           [("dollars", 57, "Liberty Head $2.50 (1840-1907)"),
                                ("dollars", 58, "Indian Head $2.50 (1908-1929)")],
    "three dollar gold":       [("dollars", 59, "Three Dollar Gold (1854-1889)")],
    "liberty half eagle":      [("dollars", 64, "Liberty Head $5 (1839-1908)")],
    "indian head half eagle":  [("dollars", 65, "Indian Head $5 (1908-1929)")],
    "half eagle":              [("dollars", 64, "Liberty Head $5 (1839-1908)")],
    "liberty eagle":           [("dollars", 67, "Liberty Head $10 (1838-1907)")],
    "indian head eagle":       [("dollars", 68, "Indian Head $10 (1907-1933)")],
    "liberty double eagle":    [("dollars", 69, "Liberty Head $20 (1850-1907)")],
    "saint gaudens":           [("dollars", 70, "Saint-Gaudens $20 (1907-1933)")],
    "saint-gaudens":           [("dollars", 70, "Saint-Gaudens $20 (1907-1933)")],
    "double eagle":            [("dollars", 69, "Liberty Head $20 (1850-1907)"),
                                ("dollars", 70, "Saint-Gaudens $20 (1907-1933)")],
    # ── Bullion ───────────────────────────────────────────────────────────
    "silver eagle":            [("dollars", 76, "Silver Eagles (1986-Date)")],
    "american silver eagle":   [("dollars", 76, "Silver Eagles (1986-Date)")],
    # ── Commemoratives ────────────────────────────────────────────────────
    "silver commemorative":    [("dollars", 71, "Silver Commemoratives (1892-1954)")],
    "gold commemorative":      [("dollars", 72, "Gold Commemoratives (1903-1926)")],
    "modern commemorative":    [("dollars", 73, "Modern Commemoratives (1982-Date)")],
}

# Mid-grade reference price priority (used when no explicit selection)
_MID_GRADE_PRIORITY = ["MS-63", "MS-64", "MS-65", "VF-20", "VF-30", "F-12", "EF-40",
                        "AU-50", "AU-58", "XF", "VF", "F"]

# ---------------------------------------------------------------------------
# Denomination lookup by (category, id).
# Face value as a formatted string, e.g. "$1.00".
# ---------------------------------------------------------------------------
_DENOMINATION: Dict[Tuple[str, int], str] = {
    # Half Cents
    **{("cents", i): "$0.005" for i in range(7, 11)},
    # Large/Small Cents
    **{("cents", i): "$0.01"  for i in range(11, 18)},
    **{("dollars", i): "$0.01" for i in [99, 100, 101]},
    # Two Cents
    ("cents", 19): "$0.02",
    # Three Cents
    ("cents", 20): "$0.03",  # Silver Three Cents
    ("cents", 21): "$0.03",  # Nickel Three Cents
    # Nickels
    **{("cents", i): "$0.05" for i in range(22, 26)},
    # Half Dimes
    ("cents", 26): "$0.05",
    ("cents", 27): "$0.05",
    # Dimes
    **{("cents", i): "$0.10" for i in range(28, 33)},
    # Twenty Cents
    ("cents", 33): "$0.20",
    # Quarters
    **{("cents", i): "$0.25" for i in range(34, 39)},
    ("dollars", 88):  "$0.25",  # State Quarters
    ("dollars", 103): "$0.25",  # ATB Quarters
    # Half Dollars
    ("cents", 39): "$0.50",   # Flowing Hair
    **{("dollars", i): "$0.50" for i in range(40, 45)},
    # Dollars (silver & modern)
    **{("dollars", i): "$1.00" for i in range(45, 54)},
    ("dollars", 76): "$1.00",   # Silver Eagles
    ("dollars", 89): "$1.00",   # Presidential Dollars
    # Gold Dollars
    ("dollars", 54): "$1.00",
    # Gold Quarter Eagles ($2.50)
    **{("dollars", i): "$2.50" for i in range(55, 59)},
    # Three Dollar Gold
    ("dollars", 59): "$3.00",
    # Four Dollar Stella
    ("dollars", 60): "$4.00",
    # Half Eagles ($5)
    **{("dollars", i): "$5.00" for i in range(61, 66)},
    # Eagles ($10)
    **{("dollars", i): "$10.00" for i in range(66, 69)},
    # Double Eagles ($20)
    ("dollars", 69): "$20.00",
    ("dollars", 70): "$20.00",
    # Commemoratives
    ("dollars", 71): "$0.50",   # Silver Commemoratives (most are half dollars)
    ("dollars", 72): "$2.50",   # Gold Commemoratives (most are $2.50)
    ("dollars", 73): "$1.00",   # Modern Commemoratives
}

# ---------------------------------------------------------------------------
# Silver content by (category, id) as a decimal (0.0–1.0).
# Some series have year-dependent values (handled in _silver_amount()).
# ---------------------------------------------------------------------------
_SILVER_FIXED: Dict[Tuple[str, int], float] = {
    # Half Cents — copper
    **{("cents", i): 0.0 for i in range(7, 11)},
    # Large/Small Cents — copper/copper-nickel
    **{("cents", i): 0.0 for i in range(11, 18)},
    **{("dollars", i): 0.0 for i in [99, 100, 101]},
    # Two Cents — bronze
    ("cents", 19): 0.0,
    # Silver Three Cents
    ("cents", 20): 0.90,
    # Nickel Three Cents
    ("cents", 21): 0.0,
    # Shield + Liberty Head nickels
    ("cents", 22): 0.0,
    ("cents", 23): 0.0,
    # Buffalo nickel
    ("cents", 24): 0.0,
    # Half Dimes — 90% silver
    ("cents", 26): 0.90,
    ("cents", 27): 0.90,
    # Early/Seated Liberty/Barber/Mercury dimes — all pre-clad, 90%
    ("cents", 28): 0.90,
    ("cents", 29): 0.90,
    ("cents", 30): 0.90,
    ("cents", 31): 0.90,
    # Twenty Cents
    ("cents", 33): 0.90,
    # Quarters (all pre-Washington types, always 90%)
    ("cents", 34): 0.90,
    ("cents", 35): 0.90,
    ("cents", 36): 0.90,
    ("cents", 37): 0.90,
    # Flowing Hair Half Dollar
    ("cents", 39): 0.90,
    # Seated Liberty/Barber/Walking Liberty/Franklin Half Dollars — always 90%
    ("dollars", 40): 0.90,
    ("dollars", 41): 0.90,
    ("dollars", 42): 0.90,
    ("dollars", 43): 0.90,
    # Early/Gobrecht/Seated Liberty/Trade dollars — 90%
    ("dollars", 45): 0.90,
    ("dollars", 46): 0.90,
    ("dollars", 47): 0.90,
    ("dollars", 48): 0.90,
    # Morgan / Peace dollars — 90%
    ("dollars", 49): 0.90,
    ("dollars", 50): 0.90,
    # Eisenhower — clad (special silver issues exist but complex; default 0%)
    ("dollars", 51): 0.0,
    # Susan B. Anthony / Sacagawea / Presidential — clad
    ("dollars", 52): 0.0,
    ("dollars", 53): 0.0,
    ("dollars", 89): 0.0,
    # Gold Dollars — no silver
    ("dollars", 54): 0.0,
    # Gold Quarter Eagles through Double Eagles — no silver
    **{("dollars", i): 0.0 for i in range(55, 71)},
    # Silver Commemoratives (1892–1954) — 90%
    ("dollars", 71): 0.90,
    # Gold Commemoratives — no silver
    ("dollars", 72): 0.0,
    # Modern Commemoratives — most are 90% silver dollar; some clad
    ("dollars", 73): 0.90,
    # Silver Eagles — .999 fine silver
    ("dollars", 76): 0.999,
    # State / ATB Quarters — clad
    ("dollars", 88):  0.0,
    ("dollars", 103): 0.0,
}

# Series with year-dependent silver content:
# (category, id) → list of (max_year_inclusive, silver_decimal)
# Applied in ascending order; first match wins.
_SILVER_BY_YEAR: Dict[Tuple[str, int], list] = {
    # Jefferson nickels: 1942–1945 wartime = 35%; all others 0%
    ("cents", 25): [(1941, 0.0), (1945, 0.35), (9999, 0.0)],
    # Roosevelt dimes: pre-1965 = 90%; 1965+ = 0%
    ("cents", 32): [(1964, 0.90), (9999, 0.0)],
    # Washington quarters: pre-1965 = 90%; 1965+ = 0%
    ("cents", 38): [(1964, 0.90), (9999, 0.0)],
    # Kennedy half dollars: 1964 = 90%; 1965–1970 = 40%; 1971+ = 0%
    ("dollars", 44): [(1964, 0.90), (1970, 0.40), (9999, 0.0)],
}


# ---------------------------------------------------------------------------
# Wikipedia article titles for series thumbnail images.
# Keyed by (category, id) matching NGC_SERIES_MAP.
# Used by _series_image_url() to fetch a representative coin photo.
# ---------------------------------------------------------------------------
_WIKIPEDIA_TITLES: Dict[Tuple[str, int], str] = {
    # Half Cents
    ("cents", 7):    "Half cent (United States coin)",
    ("cents", 8):    "Half cent (United States coin)",
    ("cents", 9):    "Half cent (United States coin)",
    ("cents", 10):   "Half cent (United States coin)",
    # Large / Early Cents
    ("cents", 11):   "Chain cent",
    ("cents", 12):   "Flowing Hair cent",
    ("cents", 13):   "Draped Bust cent",
    ("cents", 14):   "Classic Head cent",
    ("cents", 15):   "Coronet cent",
    # Small Cents
    ("cents", 16):   "Flying Eagle cent",
    ("cents", 17):   "Indian Head cent",
    ("dollars", 99): "Lincoln cent",
    ("dollars", 100):"Lincoln cent",
    ("dollars", 101):"Lincoln cent",
    # Two / Three Cents
    ("cents", 19):   "Two-cent piece (United States)",
    ("cents", 20):   "Three-cent piece (United States)",
    ("cents", 21):   "Three-cent piece (United States)",
    # Nickels
    ("cents", 22):   "Shield nickel",
    ("cents", 23):   "Liberty Head nickel",
    ("cents", 24):   "Buffalo nickel",
    ("cents", 25):   "Jefferson nickel",
    # Half Dimes
    ("cents", 26):   "Half dime",
    ("cents", 27):   "Seated Liberty half dime",
    # Dimes
    ("cents", 28):   "Draped Bust dime",
    ("cents", 29):   "Seated Liberty dime",
    ("cents", 30):   "Barber dime",
    ("cents", 31):   "Mercury dime",
    ("cents", 32):   "Roosevelt dime",
    # Twenty Cents
    ("cents", 33):   "Twenty-cent piece (United States coin)",
    # Quarters
    ("cents", 34):   "Draped Bust quarter",
    ("cents", 35):   "Seated Liberty quarter",
    ("cents", 36):   "Barber quarter",
    ("cents", 37):   "Standing Liberty quarter",
    ("cents", 38):   "Washington quarter",
    ("dollars", 88): "50 State Quarters",
    ("dollars", 103):"America the Beautiful quarters",
    # Half Dollars
    ("cents", 39):   "Flowing Hair dollar",
    ("dollars", 40): "Seated Liberty half dollar",
    ("dollars", 41): "Barber half dollar",
    ("dollars", 42): "Walking Liberty half dollar",
    ("dollars", 43): "Franklin half dollar",
    ("dollars", 44): "Kennedy half dollar",
    # Silver Dollars
    ("dollars", 45): "Flowing Hair dollar",
    ("dollars", 46): "Gobrecht dollar",
    ("dollars", 47): "Seated Liberty dollar",
    ("dollars", 48): "Trade dollar (United States)",
    ("dollars", 49): "Morgan dollar",
    ("dollars", 50): "Peace dollar",
    ("dollars", 51): "Eisenhower dollar",
    ("dollars", 52): "Susan B. Anthony dollar",
    ("dollars", 53): "Sacagawea dollar",
    ("dollars", 89): "Presidential dollar coin",
    # Gold
    ("dollars", 54): "Gold dollar",
    ("dollars", 57): "Liberty Head quarter eagle",
    ("dollars", 58): "Indian Head quarter eagle",
    ("dollars", 59): "Three-dollar piece",
    ("dollars", 64): "Liberty Head half eagle",
    ("dollars", 65): "Indian Head half eagle",
    ("dollars", 67): "Liberty Head eagle",
    ("dollars", 68): "Indian Head eagle",
    ("dollars", 69): "Liberty Head double eagle",
    ("dollars", 70): "Saint-Gaudens double eagle",
    # Bullion
    ("dollars", 76): "American Silver Eagle",
    # Commemoratives
    ("dollars", 71): "United States commemorative coins",
    ("dollars", 72): "United States commemorative coins",
    ("dollars", 73): "United States commemorative coins",
}

# Simple cache so we don't re-fetch the same Wikipedia article per run
_WIKI_IMAGE_CACHE: Dict[str, str] = {}


def _series_image_url(series_url: str) -> str:
    """
    Return a Wikipedia thumbnail URL for the coin series, or '' on failure.
    Result is cached in-process so each article is fetched at most once.
    """
    m = re.search(r"/united-states/(\w+)/(\d+)/", series_url)
    if not m:
        return ""
    key = (m.group(1), int(m.group(2)))
    if series_url in _WIKI_IMAGE_CACHE:
        return _WIKI_IMAGE_CACHE[series_url]
    article = _WIKIPEDIA_TITLES.get(key, "")
    if not article:
        _WIKI_IMAGE_CACHE[series_url] = ""
        return ""
    try:
        api_url = (
            "https://en.wikipedia.org/api/rest_v1/page/summary/"
            + article.replace(" ", "_")
        )
        resp = requests.get(
            api_url,
            headers={"User-Agent": "collectibles-manager/1.0 (educational)"},
            timeout=8,
        )
        if resp.ok:
            data = resp.json()
            thumb = data.get("thumbnail", {}).get("source", "")
            _WIKI_IMAGE_CACHE[series_url] = thumb
            return thumb
    except Exception as e:
        logger.debug("Wikipedia image fetch failed for %r: %s", article, e)
    _WIKI_IMAGE_CACHE[series_url] = ""
    return ""


# Per-coin NGC coin-explorer image cache: coin_explorer_url → (obverse_url, reverse_url)
_NGC_COIN_IMG_CACHE: Dict[str, Tuple[str, str]] = {}

# Max unique coin explorer URLs to fetch images for per search request
_MAX_IMG_LOOKUPS = 20

# Strike type → ordered list of variant labels (position 0=base, 1=PL/Cameo, 2=DPL/DeepCameo)
_STRIKE_VARIANTS: Dict[str, List[str]] = {
    "ms":  ["MS", "MS PL", "MS DPL"],
    "sp":  ["SP", "SP PL", "SP DPL"],
    "sms": ["SMS"],
    "pf":  ["PF", "PF Cameo", "PF Deep Cameo"],
    "pr":  ["PF", "PF Cameo", "PF Deep Cameo"],
}


def _coin_type_label(strike_type: str, position: int) -> str:
    """Return the human label for a coin type given strike type and position in its group."""
    variants = _STRIKE_VARIANTS.get(strike_type.lower(), [strike_type.upper()])
    return variants[min(position, len(variants) - 1)]


def _fetch_ngc_coin_images(coin_explorer_url: str) -> Tuple[str, str]:
    """
    Fetch obverse + reverse S3 image URLs from the NGC coin explorer JSON API.

    coin_explorer_url: e.g.
      https://www.ngccoin.com/coin-explorer/united-states/dollars/
                               morgan-dollars-1878-1921/17248/1897-o-1-ms/

    The NGC internal API is at:
      https://www.ngccoin.com/coin-explorer/data/coins/{coinID}/

    Returns (obverse_url, reverse_url); either string may be '' on failure.
    Results are cached in _NGC_COIN_IMG_CACHE.
    """
    if coin_explorer_url in _NGC_COIN_IMG_CACHE:
        return _NGC_COIN_IMG_CACHE[coin_explorer_url]

    # Extract the numeric CoinID from URL path. Two possible formats:
    #   /coin-explorer/united-states/{cat}/{series-slug}/{coinID}/{desc}/
    #   /redirects/coin-explorer/{coinID}/
    m = re.search(r"/coin-explorer/[^/]+/[^/]+/[^/]+/(\d+)/", coin_explorer_url)
    if not m:
        m = re.search(r"/redirects/coin-explorer/(\d+)/", coin_explorer_url)
    if not m:
        _NGC_COIN_IMG_CACHE[coin_explorer_url] = ("", "")
        return ("", "")

    coin_id = m.group(1)
    api_url = f"https://www.ngccoin.com/coin-explorer/data/coins/{coin_id}/"

    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=10)
        if resp.ok:
            data = resp.json()
            obv = data.get("ObverseImageURL") or ""
            rev = data.get("ReverseImageURL") or ""
            result = (obv, rev)
            _NGC_COIN_IMG_CACHE[coin_explorer_url] = result
            logger.debug(
                "NGC coin images for coinID=%s: obv=%s rev=%s",
                coin_id, "✓" if obv else "✗", "✓" if rev else "✗",
            )
            return result
    except Exception as e:
        logger.debug("NGC coin image fetch failed for coinID=%s: %s", coin_id, e)

    _NGC_COIN_IMG_CACHE[coin_explorer_url] = ("", "")
    return ("", "")


def _denomination_for(series_url: str) -> str:
    """Return face value string for a series URL, e.g. '$1.00'."""
    m = re.search(r"/united-states/(\w+)/(\d+)/", series_url)
    if not m:
        return ""
    return _DENOMINATION.get((m.group(1), int(m.group(2))), "")


def _silver_for(series_url: str, year_str: str) -> Optional[float]:
    """Return silver content as decimal (0.0–1.0) or None if unknown."""
    m = re.search(r"/united-states/(\w+)/(\d+)/", series_url)
    if not m:
        return None
    key = (m.group(1), int(m.group(2)))
    year = int(year_str) if year_str.isdigit() else 0

    # Check year-dependent table first
    if key in _SILVER_BY_YEAR:
        for max_year, silver in _SILVER_BY_YEAR[key]:
            if year <= max_year:
                return silver

    return _SILVER_FIXED.get(key)  # None if series not in either table


def _format_grade(grade_attr: str, strike_type: str) -> str:
    """
    Convert NGC grade attribute value to a human label.
      'PrAg','G','VG','F','VF','XF'  → kept as-is
      '50'–'58'                       → 'AU-{n}'
      '60'–'70', strike=='pf'         → 'PF-{n}'
      '60'–'70', otherwise            → 'MS-{n}'
    """
    if re.match(r"^\d+$", grade_attr):
        n = int(grade_attr)
        if 50 <= n <= 58:
            return f"AU-{n}"
        elif 60 <= n <= 70:
            prefix = "PF" if strike_type in ("pf", "pr") else "MS"
            return f"{prefix}-{n}"
    return grade_attr  # text grade (PrAg, G, VG, etc.)


def _extract_date_label(raw_text: str) -> str:
    """
    Census cell text like 'Yr XFVarYr XFVar $1 MS...' → 'Yr XFVar'.
    The label is duplicated in the cell text; find second occurrence of year.
    """
    year_m = re.search(r"\d{4}", raw_text)
    if not year_m:
        return raw_text[:20].strip()
    year = year_m.group()
    start = year_m.start()
    # Find where year appears again
    second = raw_text.find(year, start + 1)
    if second > start:
        return raw_text[start:second].strip()
    # Fallback: everything before the '$' sign
    dollar_pos = raw_text.find("$")
    if dollar_pos > start:
        return raw_text[start:dollar_pos].strip()
    return raw_text[start:start + 20].strip()


def _coin_id(series: str, year: str, mint: str) -> str:
    key = f"ngc-{series.lower().strip()}-{year.strip()}-{mint.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _to_price(text: str) -> Optional[float]:
    """Parse '$1,234' or 'N/A' or '—' → float, or None."""
    cleaned = re.sub(r"[^0-9.]", "", text.replace(",", ""))
    if not cleaned:
        return None
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def _fetch(url: str, timeout: int = 20) -> Optional[BeautifulSoup]:
    """GET with browser headers; raise on HTTP error."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    logger.debug("NGC fetch OK: %s (%d bytes)", url, len(resp.content))
    return BeautifulSoup(resp.text, "html.parser")


def _lookup_series(coin_name: str) -> List[Tuple[str, str]]:
    """
    Return (human_label, url) pairs for coin_name using NGC_SERIES_MAP.
    Falls back to fetching the index page only if map misses.
    """
    name_lower = coin_name.lower().strip()
    results: List[Tuple[str, str]] = []
    seen: set = set()

    for key, entries in NGC_SERIES_MAP.items():
        if key in name_lower or name_lower in key:
            for cat, cid, label in entries:
                url = f"{NGC_PRICE_GUIDE}/{cat}/{cid}/"
                if url not in seen:
                    seen.add(url)
                    results.append((label, url))

    if results:
        logger.debug("NGC map hit for %r: %d series", coin_name, len(results))
        return results[:4]

    # Dynamic fallback: scrape the index page (may be JS-rendered, best effort)
    logger.debug("NGC: %r not in map, trying index", coin_name)
    try:
        soup = _fetch(NGC_PRICE_GUIDE)
        if soup:
            tokens = [t for t in name_lower.split() if len(t) > 2]
            for a in soup.find_all("a", href=True):
                href: str = a["href"]
                text: str = a.get_text(strip=True)
                if not any(t in text.lower() for t in tokens):
                    continue
                full_url = href if href.startswith("http") else NGC_BASE + href
                if full_url not in seen:
                    seen.add(full_url)
                    results.append((text, full_url))
    except Exception as e:
        logger.warning("NGC index fetch failed: %s", e)

    return results[:5]


def _build_census_map(series_url: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Fetch the series page and build two maps from the NGC Census table (Table 2):
      - coin_id → date label  (e.g. "1921 D")
      - coin_id → per-coin census URL  (href from the anchor in each cell, if present)

    Returns ({}, {}) on failure.
    """
    date_map: Dict[str, str] = {}
    url_map:  Dict[str, str] = {}
    try:
        soup = _fetch(series_url)
        if not soup:
            return date_map, url_map
        tables = soup.find_all("table")
        if len(tables) < 2:
            return date_map, url_map
        census_table = tables[1]
        for row in census_table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            first = cells[0]
            parent_id = first.get("parent-coin-id")
            if parent_id:
                raw = first.get_text(strip=True)
                date_map[parent_id] = _extract_date_label(raw)
                # Capture the per-coin census URL from the anchor tag if NGC provides one
                a = first.find("a", href=True)
                if a:
                    href = a["href"]
                    if href.startswith("/"):
                        href = "https://www.ngccoin.com" + href
                    url_map[parent_id] = href
        logger.debug(
            "NGC census map: %d date entries, %d url entries for %s",
            len(date_map), len(url_map), series_url,
        )
        return date_map, url_map
    except Exception as e:
        logger.warning("NGC census map fetch failed for %s: %s", series_url, e)
        return date_map, url_map


def _fetch_price_data(data_url: str, timeout: int = 45) -> Optional[BeautifulSoup]:
    """
    Fetch the NGC price-guide /data/ endpoint which returns the full
    price table as an HTML fragment (no JS rendering needed).

    The /data/ endpoint: {series_url}data/
    e.g. https://www.ngccoin.com/price-guide/united-states/dollars/49/data/
    """
    resp = requests.get(data_url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    logger.debug("NGC /data/ fetch OK: %s (%d bytes)", data_url, len(resp.content))
    return BeautifulSoup(resp.text, "html.parser")


def _parse_price_table(
    soup: BeautifulSoup,
    coin_id_to_date: Dict[str, str],
    coin_id_to_url: Dict[str, str],
    series_label: str,
    year_filter: str,
    mint_filter: str,
    series_url: str,
    series_image: str = "",
    group_pos: Optional[Dict[Tuple[str, str], int]] = None,
) -> List[Dict]:
    """
    Parse the NGC price-guide HTML price table.

    Works on both:
      - The main page's Table 3 (partial — initial view only)
      - The /data/ endpoint response (complete — all years)

    Row structure:
      class = [strike_type, year]  e.g. ['ms', '1878']
      base-class cells: grade="{grade}" coin-id="{id}" → price text
    """
    if group_pos is None:
        group_pos = {}

    table = soup.find("table")
    if not table:
        return []

    coins: List[Dict] = []
    for row in table.find_all("tr"):
        row_class = row.get("class", [])
        if not row_class or len(row_class) < 2:
            continue  # skip header row

        strike_type = row_class[0].lower()  # 'ms', 'pf', 'sp', 'sms', etc.
        row_year    = row_class[1]           # '1878', '2020', etc.

        if year_filter and row_year != year_filter.strip():
            continue

        # Collect base-grade cells only (skip star/plus/star-plus variants)
        prices_map: Dict[str, float] = {}
        row_coin_id: Optional[str] = None
        for cell in row.find_all(["td", "th"]):
            cls = cell.get("class", [])
            if "base" not in cls:
                continue
            grade_attr = cell.get("grade")
            cid        = cell.get("coin-id")
            price_text = cell.get_text(strip=True)
            if grade_attr and cid:
                price = _to_price(price_text)
                if price is not None:
                    grade_label = _format_grade(grade_attr, strike_type)
                    prices_map[grade_label] = price
                    if row_coin_id is None:
                        row_coin_id = cid

        if not prices_map:
            continue

        # ── Resolve date label ─────────────────────────────────────────────
        date_label = ""
        if row_coin_id and row_coin_id in coin_id_to_date:
            date_label = coin_id_to_date[row_coin_id]
        if not date_label:
            date_label = row_year  # fallback: just the year

        # ── Track position within (date_label, strike_type) group for coin type ──
        gkey = (date_label, strike_type)
        pos  = group_pos.get(gkey, 0)
        group_pos[gkey] = pos + 1
        coin_type = _coin_type_label(strike_type, pos)

        # ── Extract year and mint mark ─────────────────────────────────────
        year_m = re.search(r"(\d{4})", date_label)
        extracted_year = year_m.group(1) if year_m else row_year
        # NGC uses space before mint mark: "1878 S", "1921 D", "1880 CC"
        mint_m = re.search(r"\d{4}\s+([A-Z]{1,2})\b", date_label)
        extracted_mint = mint_m.group(1) if mint_m else ""

        if mint_filter and extracted_mint.upper() != mint_filter.upper().strip():
            continue

        # ── Price aggregation ──────────────────────────────────────────────
        prices_vals = list(prices_map.values())
        price_low    = min(prices_vals)
        price_market = max(prices_vals)

        price_usd: float = 0.0
        for grade in _MID_GRADE_PRIORITY:
            if grade in prices_map:
                price_usd = prices_map[grade]
                break
        if price_usd == 0.0:
            price_usd = sorted(prices_vals)[len(prices_vals) // 2]

        # ── Coin metadata ──────────────────────────────────────────────────
        denomination = _denomination_for(series_url)
        silver       = _silver_for(series_url, extracted_year)

        coins.append({
            "id":              _coin_id(series_label, extracted_year, extracted_mint),
            "game":            "Coins",
            "name":            series_label,
            "set":             series_label,
            "set_code":        series_url,   # series price-guide URL (for Series column link)
            "year":            extracted_year,
            "card_number":     date_label,
            "image_url":       series_image,
            "image_url_back":  "",
            # Per-coin census URL if NGC provides one; otherwise fall back to series URL
            "link":            coin_id_to_url.get(row_coin_id or "", series_url) or series_url,
            "price_usd":       price_usd,
            "price_usd_foil":  0.0,
            "price_usd_etched":0.0,
            "price_low":       price_low,
            "price_mid":       None,
            "price_market":    price_market,
            "prices_map":      prices_map,
            "has_nonfoil":     False,
            "has_foil":        False,
            "source":          "NGC Price Guide",
            "artist":          "",
            "variant":         "",
            "quantity":        1,
            # Coin-specific metadata
            "coin_type":       coin_type,
            "denomination":    denomination or None,
            "country":         "USA",
            "coin_or_bill":    "Coin",
            "silver_amount":   silver,
            "mint_mark":       extracted_mint,
        })

    return coins


def search_ngc_coins(
    coin_name: str,
    year: str = "",
    mint_mark: str = "",
) -> Tuple[List[Dict], int, int, str]:
    """
    Search NGC Price Guide for coins matching coin_name.
    Optionally filter by year and/or mint_mark.

    Strategy:
      1. Look up series URL(s) from NGC_SERIES_MAP (or index page fallback).
      2. Fetch the series main page → build coin-id → date label map (census table).
      3. Fetch {series_url}data/ → full price table HTML (all years, no JS needed).
      4. Parse and return all matching coin rows.

    Returns (coins, shown, total, source_label).
    Raises on network failure so the caller can fall back to USA Coin Book.
    """
    series_links = _lookup_series(coin_name)
    if not series_links:
        logger.info("NGC: no series found for %r", coin_name)
        return [], 0, 0, "NGC Price Guide"

    all_coins: List[Dict] = []
    for series_label, series_url in series_links:
        try:
            # Step 1: Build coin-id → date label and coin-id → census URL from main page
            coin_id_to_date, coin_id_to_url = _build_census_map(series_url)

            # Step 2: Fetch series thumbnail image from Wikipedia (cached per series)
            series_image = _series_image_url(series_url)

            # Step 3: Fetch the full price table via the /data/ endpoint
            data_url = series_url.rstrip("/") + "/data/"
            soup = _fetch_price_data(data_url)
            if not soup:
                continue

            group_pos: Dict[Tuple[str, str], int] = {}
            coins = _parse_price_table(
                soup, coin_id_to_date, coin_id_to_url,
                series_label, year, mint_mark, series_url,
                series_image=series_image,
                group_pos=group_pos,
            )

            # ── Enrich with per-coin NGC S3 images (obverse + reverse) ──
            # Uses the NGC coin-explorer JSON API (no JS rendering needed).
            # Keyed by coin explorer URL so each unique coin is fetched once.
            seen_links: Set[str] = set()
            img_map: Dict[str, Tuple[str, str]] = {}
            lookups = 0
            for coin in coins:
                link = coin.get("link", "")
                # Only call the API if we have a per-coin URL (not the series fallback)
                if link and link != series_url and link not in seen_links:
                    seen_links.add(link)
                    if lookups < _MAX_IMG_LOOKUPS:
                        obv, rev = _fetch_ngc_coin_images(link)
                        img_map[link] = (obv or series_image, rev)
                        lookups += 1
                    else:
                        img_map[link] = (series_image, "")
            for coin in coins:
                link = coin.get("link", "")
                obv, rev = img_map.get(link, (series_image, ""))
                coin["image_url"]      = obv
                coin["image_url_back"] = rev

            # ── Merge coins with same (year, mint_mark, card_number) into one card ──
            # Position within each group determines the coin type (MS, MS PL, MS DPL etc.)
            from collections import OrderedDict as _OD
            merged: "_OD[Tuple, Dict]" = _OD()
            for coin in coins:
                key = (coin["year"], coin.get("mint_mark", ""), coin["card_number"])
                if key not in merged:
                    merged[key] = {
                        **coin,
                        "coin_type_options": [],
                        "coin_types_data": {},
                    }
                m = merged[key]
                ctype = coin.get("coin_type", "")
                m["coin_type_options"].append(ctype)
                m["coin_types_data"][ctype] = {
                    "prices_map":   coin["prices_map"],
                    "price_usd":    coin["price_usd"],
                    "price_low":    coin["price_low"],
                    "price_market": coin["price_market"],
                    "link":         coin["link"],
                    "image_url":    coin["image_url"],
                    "image_url_back": coin["image_url_back"],
                }
            coins = list(merged.values())

            all_coins.extend(coins)
            logger.debug("NGC: %d coins from %r", len(coins), series_label)
            if not coins:
                logger.info(
                    "NGC: /data/ fetched for %s but no prices parsed", series_url
                )
        except Exception as e:
            logger.warning("NGC: error for %r at %s: %s", series_label, series_url, e)

    return all_coins, len(all_coins), len(all_coins), "NGC Price Guide"
