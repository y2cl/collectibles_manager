"""
Pokémon TCG API client.
Extracted from collectiman.py::search_pokemon_tcg — all st.* calls removed.
"""
import logging
from typing import List, Dict, Tuple, Optional

import requests

logger = logging.getLogger(__name__)


def _pluck(pr: Dict, key: str) -> float:
    try:
        return float((pr or {}).get(key) or 0)
    except Exception:
        return 0.0


def search_pokemon_tcg(
    card_name: str,
    set_hint: str = "",
    number: str = "",
    api_key: str = "",
    api_url: str = "https://api.pokemontcg.io/v2/cards",
    fallback_enabled: bool = True,
) -> Tuple[List[Dict], int, int, str]:
    """
    Search the Pokémon TCG API for cards.
    Returns (cards, shown_count, total_count, source_label).
    """
    try:
        qs: List[str] = []
        nm = (card_name or "").strip()
        if nm:
            safe_nm = nm.replace('"', '\\"')
            qs.append(f'name:"{safe_nm}"')
        sh = (set_hint or "").strip()
        if sh:
            if len(sh) <= 5 and sh.upper() == sh:
                qs.append(f"set.id:{sh}")
            else:
                qs.append(f'set.name:"{sh}"')
        num = (number or "").strip()
        if num:
            qs.append(f"number:{num}")

        q = " ".join(qs) if qs else nm
        params = {"q": q, "orderBy": "set.releaseDate"}

        headers: Dict[str, str] = {}
        if api_key:
            headers["X-Api-Key"] = api_key

        resp = requests.get(api_url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json() or {}
        items = data.get("data", [])

        # Retry without number if no results, then client-side prefix match
        if not items and num:
            qs_no_num = [s for s in qs if not s.startswith("number:")]
            params2 = {"q": " ".join(qs_no_num) or nm, "orderBy": "set.releaseDate"}
            resp2 = requests.get(api_url, params=params2, headers=headers, timeout=30)
            if resp2.ok:
                data2 = resp2.json() or {}
                items = [c for c in (data2.get("data", []) or []) if str(c.get("number", "")).startswith(num)]

        cards: List[Dict] = []
        for c in items:
            try:
                set_obj = c.get("set", {}) or {}
                set_name = set_obj.get("name", "")
                set_code = set_obj.get("id", "")
                released = set_obj.get("releaseDate", "")
                year = str(released)[:4] if released else ""

                imgs = c.get("images") or {}
                img_url = imgs.get("small") or imgs.get("large") or ""

                link = (
                    (c.get("tcgplayer") or {}).get("url")
                    or (c.get("cardmarket") or {}).get("url")
                    or f"https://pokemontcg.io/card/{c.get('id', '')}"
                )

                prices = ((c.get("tcgplayer") or {}).get("prices") or {})
                market_price = 0.0
                prices_map: Dict = {}
                for k in ["normal", "holofoil", "reverseHolofoil", "1stEditionHolofoil",
                          "1stEdition", "unlimited", "unlimitedHolofoil"]:
                    p = prices.get(k) or {}
                    low_v = _pluck(p, "low")
                    mid_v = _pluck(p, "mid")
                    mkt_v = _pluck(p, "market")
                    if any([low_v, mid_v, mkt_v]):
                        prices_map[k] = {"low": low_v, "mid": mid_v, "market": mkt_v}
                        market_price = mkt_v or market_price

                # Carry the raw tcgplayer object so updatedAt is available
                tcgplayer_raw = c.get("tcgplayer") or {}

                card = {
                    "game": "Pokémon",
                    "name": c.get("name", ""),
                    "set": set_name,
                    "set_code": set_code,
                    "year": year,
                    "card_number": c.get("number", ""),
                    "image_url": img_url,
                    "link": link,
                    "price_usd": market_price,
                    "quantity": 1,
                    "variant": "",
                    "prices_map": prices_map,
                    "tcgplayer": tcgplayer_raw,
                    "source": "Pokémon TCG",
                }

                if fallback_enabled:
                    try:
                        from ..legacy.fallback_manager import store_pokemon_card, store_pokemon_set
                        store_pokemon_card(c)
                        if set_obj:
                            store_pokemon_set(set_obj)
                    except Exception:
                        pass

                cards.append(card)
            except Exception:
                continue

        return cards, len(cards), len(items), "Pokémon TCG"

    except Exception as e:
        logger.error("Pokémon TCG search error: %s", e)
        return [], 0, 0, f"Pokémon TCG Error: {str(e)}"
