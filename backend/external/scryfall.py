"""
Scryfall API client for MTG card search.
Extracted from collectiman.py::search_mtg_scryfall — all st.* calls removed.
"""
import re
import logging
from typing import List, Dict, Tuple

import requests

logger = logging.getLogger(__name__)


def _to_float(v) -> float:
    try:
        return float(v) if v not in (None, "", "None") else 0.0
    except Exception:
        return 0.0


def search_mtg_scryfall(
    card_name: str,
    set_hint: str = "",
    collector_number: str = "",
    fallback_enabled: bool = True,
) -> Tuple[List[Dict], int, int, str]:
    """
    Search Scryfall for MTG cards.
    Returns (cards, shown_count, total_count, source_label).
    Optionally stores results in the offline fallback cache.
    """
    try:
        q = card_name.strip()
        if set_hint.strip():
            q = f"{q} {set_hint.strip()}"
        if collector_number and str(collector_number).strip():
            q = f"{q} cn:{str(collector_number).strip()}"

        url = "https://api.scryfall.com/cards/search"
        attempts: List[Tuple[str, Dict]] = [
            ("primary", {"q": q, "order": "released", "unique": "prints"}),
        ]
        if card_name.strip():
            attempts.append(("fuzzy", {"q": f'name~"{card_name.strip()}"', "order": "released", "unique": "prints"}))
        token = card_name.strip().split(" ")[0] if card_name.strip() else ""
        if token:
            attempts.append(("wildcard", {"q": f"name:{token}*", "order": "released", "unique": "prints"}))

        items: List[Dict] = []
        which = "primary"
        for tag, params in attempts:
            logger.debug("Scryfall attempt '%s' params=%s", tag, params)
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json() or {}
            items = data.get("data", []) or []
            if items:
                which = tag
                break

        cards: List[Dict] = []
        for c in items:
            try:
                set_name = c.get("set_name", "")
                released = c.get("released_at", "")
                m4 = re.search(r"(19\d{2}|20\d{2})", str(released))
                year = m4.group(1) if m4 else str(released)

                img = None
                img_back = None
                iu = c.get("image_uris") or {}
                faces = c.get("card_faces") or []
                if iu:
                    img = iu.get("normal") or iu.get("large") or iu.get("small")
                elif faces and isinstance(faces, list):
                    # Double-faced card: front from faces[0], back from faces[1]
                    iu_front = faces[0].get("image_uris") or {}
                    img = iu_front.get("normal") or iu_front.get("large") or iu_front.get("small")
                if isinstance(faces, list) and len(faces) > 1:
                    iu_back = faces[1].get("image_uris") or {}
                    img_back = iu_back.get("normal") or iu_back.get("large") or iu_back.get("small")

                prices = c.get("prices") or {}
                has_nonfoil = bool(c.get("nonfoil"))
                has_foil = bool(c.get("foil"))

                artist = c.get("artist") or (
                    (c.get("card_faces") or [{}])[0].get("artist", "")
                    if isinstance(c.get("card_faces"), list) and c.get("card_faces")
                    else ""
                )

                card = {
                    "game": "Magic: The Gathering",
                    "name": c.get("name", ""),
                    "set": set_name,
                    "set_code": c.get("set", ""),
                    "year": year,
                    "artist": artist,
                    "card_number": c.get("collector_number", ""),
                    "price_usd": _to_float(prices.get("usd")),
                    "price_usd_foil": _to_float(prices.get("usd_foil")),
                    "price_usd_etched": _to_float(prices.get("usd_etched")),
                    "image_url": img or "",
                    "image_url_back": img_back or "",
                    "link": c.get("scryfall_uri", ""),
                    "quantity": 1,
                    "variant": "",
                    "source": "Scryfall",
                    "has_nonfoil": has_nonfoil,
                    "has_foil": has_foil,
                }
                cards.append(card)

                # Persist to offline fallback cache
                if fallback_enabled:
                    try:
                        from ..legacy.fallback_manager import store_mtg_card
                        store_mtg_card(c)
                    except Exception:
                        pass
            except Exception:
                continue

        source_label = "Scryfall" if which == "primary" else f"Scryfall ({which})"
        logger.debug("Scryfall done: which='%s', results=%d", which, len(items))
        return cards, len(cards), len(items), source_label

    except Exception as e:
        logger.error("Scryfall search error: %s", e)
        return [], 0, 0, f"Scryfall Error: {str(e)}"
