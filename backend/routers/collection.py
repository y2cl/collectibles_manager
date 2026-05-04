"""
Collection endpoints: CRUD for collection cards.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.card import CollectionCard
from ..models.owner import Owner
from ..models.settings import AppSettings
from ..schemas.card import (
    CollectionCardCreate, CollectionCardRead, CollectionCardUpdate,
    BulkDeleteRequest, BulkMoveRequest, BulkRefreshRequest,
    CollectionResponse, CollectionStats,
    MtgCardSummary, MtgCollectionResponse,
)
from ..services.collection_service import add_card

router = APIRouter(prefix="/api/collection", tags=["collection"])


def _get_settings(db: Session) -> AppSettings:
    row = db.query(AppSettings).first()
    if not row:
        row = AppSettings()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _require_owner(db: Session, owner_id_slug: str) -> Owner:
    owner = db.query(Owner).filter(Owner.owner_id == owner_id_slug).first()
    if not owner:
        raise HTTPException(status_code=404, detail=f"Owner '{owner_id_slug}' not found")
    return owner


@router.get("/suggestions")
def get_suggestions(
    owner_id: str = Query(...),
    profile_id: str = Query("default"),
    game: str = Query("Sports Cards"),
    db: Session = Depends(get_db),
):
    """Return unique field values for autocomplete datalists."""
    owner = _require_owner(db, owner_id)
    cards = db.query(CollectionCard).filter(
        CollectionCard.owner_id == owner.id,
        CollectionCard.profile_id == profile_id,
        CollectionCard.game == game,
    ).all()

    def uniq(vals):
        return sorted({v.strip() for v in vals if v and v.strip()})

    # Also pull set/insert names from the sports catalog so newly-defined sets
    # appear in autocomplete even before any cards are added
    catalog_sets: list = []
    catalog_inserts: list = []
    if game == "Sports Cards":
        from ..models.sports_set import SportsCardSet
        cat_rows = db.query(SportsCardSet).filter(
            SportsCardSet.owner_id == owner.id,
            SportsCardSet.profile_id == profile_id,
        ).all()
        catalog_sets    = [r.set_name    for r in cat_rows if r.set_name]
        catalog_inserts = [r.insert_name for r in cat_rows if r.insert_name]

    return {
        "players":          uniq(c.name             for c in cards),
        "sets":             uniq(list(c.set_name for c in cards) + catalog_sets),
        "inserts":          uniq(list(c.variant  for c in cards) + catalog_inserts),
        "grading_companies": uniq(c.grading_company  for c in cards if c.grading_company),
    }


@router.get("", response_model=CollectionResponse)
def get_collection(
    owner_id: str = Query(...),
    profile_id: str = Query("default"),
    game: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    owner = _require_owner(db, owner_id)
    q = db.query(CollectionCard).filter(
        CollectionCard.owner_id == owner.id,
        CollectionCard.profile_id == profile_id,
    )
    if game:
        q = q.filter(CollectionCard.game == game)
    cards = q.order_by(CollectionCard.timestamp.desc()).all()

    total_cards = sum(c.quantity or 1 for c in cards)
    unique_cards = len(cards)
    unique_sets = len({f"{c.year} {c.set_name}" for c in cards})
    total_value = sum((c.price_usd or 0) * (c.quantity or 1) for c in cards)

    return CollectionResponse(
        cards=cards,
        stats=CollectionStats(
            total_cards=total_cards,
            unique_cards=unique_cards,
            unique_sets=unique_sets,
            total_value=round(total_value, 2),
        ),
    )


@router.get("/mtg", response_model=MtgCollectionResponse)
def get_mtg_collection(
    owner_id: str = Query(...),
    profile_id: str = Query("default"),
    set_code: Optional[str] = Query(None, description="Filter by Scryfall set code"),
    name: Optional[str] = Query(None, description="Filter by partial card name (case-insensitive)"),
    db: Session = Depends(get_db),
):
    """Return MTG cards from the collection, scoped for cube/deck building."""
    owner = _require_owner(db, owner_id)
    q = db.query(CollectionCard).filter(
        CollectionCard.owner_id == owner.id,
        CollectionCard.profile_id == profile_id,
        CollectionCard.game == "Magic: The Gathering",
    )
    if set_code:
        q = q.filter(CollectionCard.set_code == set_code.lower())
    if name:
        q = q.filter(CollectionCard.name.ilike(f"%{name}%"))
    cards = q.order_by(CollectionCard.name).all()

    return MtgCollectionResponse(
        cards=cards,
        total_cards=sum(c.quantity or 1 for c in cards),
        unique_cards=len(cards),
    )


@router.post("/cards", response_model=CollectionCardRead, status_code=201)
def add_card_endpoint(payload: CollectionCardCreate, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    cfg = settings.api_source_config or {}
    duplicate_strategy = settings.duplicate_strategy or "merge"
    paid_merge_strategy = settings.paid_merge_strategy or "sum"

    card_data = payload.model_dump()
    result = add_card(
        db,
        owner_id_slug=payload.owner_id,
        profile_id=payload.profile_id,
        card_data=card_data,
        duplicate_strategy=duplicate_strategy,
        paid_merge_strategy=paid_merge_strategy,
    )
    return result


@router.patch("/cards/{card_id}", response_model=CollectionCardRead)
def update_card(card_id: int, payload: CollectionCardUpdate, db: Session = Depends(get_db)):
    card = db.query(CollectionCard).filter(CollectionCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(card, field, value)

    db.commit()
    db.refresh(card)
    return card


@router.delete("/cards/{card_id}", status_code=200)
def delete_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(CollectionCard).filter(CollectionCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(card)
    db.commit()
    return {"deleted": True}


@router.delete("/cards", status_code=200)
def bulk_delete_cards(payload: BulkDeleteRequest, db: Session = Depends(get_db)):
    owner = _require_owner(db, payload.owner_id)
    deleted = (
        db.query(CollectionCard)
        .filter(
            CollectionCard.owner_id == owner.id,
            CollectionCard.profile_id == payload.profile_id,
            CollectionCard.id.in_(payload.card_ids),
        )
        .all()
    )
    count = len(deleted)
    for card in deleted:
        db.delete(card)
    db.commit()
    return {"deleted_count": count}


@router.post("/cards/move", status_code=200)
def bulk_move_cards(payload: BulkMoveRequest, db: Session = Depends(get_db)):
    target_owner = _require_owner(db, payload.target_owner_id)
    cards = db.query(CollectionCard).filter(CollectionCard.id.in_(payload.card_ids)).all()
    for card in cards:
        card.owner_id = target_owner.id
        card.profile_id = payload.target_profile_id
    db.commit()
    return {"moved": len(cards)}


@router.post("/cards/refresh", status_code=200)
def bulk_refresh_cards(payload: BulkRefreshRequest, db: Session = Depends(get_db)):
    import requests as _requests

    def _to_f(v) -> Optional[float]:
        """Return float if v is a non-empty, non-zero value; else None."""
        try:
            f = float(v)
            return f if f else None
        except (TypeError, ValueError):
            return None

    def _refresh_mtg(card: CollectionCard) -> str:
        """Fetch current prices and rich MTG data from Scryfall for the card's stored variant."""
        # Prefer exact set+collector lookup; fall back to fuzzy name search.
        if card.set_code and card.card_number:
            url = f"https://api.scryfall.com/cards/{card.set_code.lower()}/{card.card_number}"
            resp = _requests.get(url, timeout=15)
            if not resp.ok:
                resp = _requests.get(
                    "https://api.scryfall.com/cards/named",
                    params={"fuzzy": card.name, **({"set": card.set_code} if card.set_code else {})},
                    timeout=15,
                )
        else:
            resp = _requests.get(
                "https://api.scryfall.com/cards/named",
                params={"fuzzy": card.name, **({"set": card.set_code} if card.set_code else {})},
                timeout=15,
            )

        if not resp.ok:
            return f"Scryfall {resp.status_code}: {resp.text[:120]}"

        data = resp.json()
        prices = data.get("prices") or {}
        usd        = _to_f(prices.get("usd"))
        usd_foil   = _to_f(prices.get("usd_foil"))
        usd_etched = _to_f(prices.get("usd_etched"))

        # Always refresh all stored price fields
        if usd:        card.price_usd        = usd
        if usd_foil:   card.price_usd_foil   = usd_foil
        if usd_etched: card.price_usd_etched  = usd_etched

        # Set price_usd to the price for this card's specific variant so the
        # collection table always shows the right market value.
        variant = (card.variant or "nonfoil").lower()
        if variant == "foil" and usd_foil:
            card.price_usd = usd_foil
        elif variant == "etched" and usd_etched:
            card.price_usd = usd_etched
        elif usd:
            card.price_usd = usd

        # Update rich MTG data fields
        card.scryfall_id = data.get("id") or card.scryfall_id
        card.mana_cost = data.get("mana_cost") or card.mana_cost
        card.type_line = data.get("type_line") or card.type_line
        card.oracle_text = data.get("oracle_text") or card.oracle_text
        card.keywords = ";".join(data.get("keywords", [])) if data.get("keywords") else card.keywords
        card.power = data.get("power") or card.power
        card.toughness = data.get("toughness") or card.toughness
        card.rarity = data.get("rarity") or card.rarity
        card.color_identity = "".join(data.get("color_identity", [])) if data.get("color_identity") else card.color_identity
        card.finish = variant if variant in ["foil", "etched", "nonfoil"] else card.finish

        return ""

    def _refresh_pokemon(card: CollectionCard) -> str:
        """Fetch current prices from the Pokémon TCG API for the card's stored variant."""
        params: dict = {"q": f'name:"{card.name}"'}
        if card.set_code:
            params["q"] += f" set.id:{card.set_code}"
        if card.card_number:
            params["q"] += f" number:{card.card_number}"

        resp = _requests.get("https://api.pokemontcg.io/v2/cards", params=params, timeout=15)
        if not resp.ok:
            return f"PokémonTCG {resp.status_code}: {resp.text[:120]}"

        items = resp.json().get("data") or []
        if not items:
            return "no results"

        tcg = items[0].get("tcgplayer") or {}
        prices_raw = tcg.get("prices") or {}

        # Try the stored variant first (e.g. "holofoil", "normal", "reverseHolofoil")
        variant = card.variant or ""
        variant_entry = prices_raw.get(variant) or {}
        price = _to_f(variant_entry.get("market")) or _to_f(variant_entry.get("mid"))

        PKMN_VARIANT_ORDER = [
            "normal", "holofoil", "reverseHolofoil",
            "unlimited", "unlimitedHolofoil",
            "1stEdition", "1stEditionHolofoil",
        ]
        matched_key = variant if variant_entry else next(
            (k for k in PKMN_VARIANT_ORDER if prices_raw.get(k)), ""
        )
        if not price:
            # Variant not found or has no price — fall back to best available market price
            for key in PKMN_VARIANT_ORDER:
                entry = prices_raw.get(key) or {}
                p = _to_f(entry.get("market")) or _to_f(entry.get("mid"))
                if p:
                    price = p
                    matched_key = key
                    break

        if price:
            card.price_usd = price
            # Also store low/mid/market from the matched variant
            matched = prices_raw.get(matched_key) or {}
            if isinstance(matched, dict):
                if p := _to_f(matched.get("low")):    card.price_low    = p
                if p := _to_f(matched.get("mid")):    card.price_mid    = p
                if p := _to_f(matched.get("market")): card.price_market = p

        return ""

    updated = 0
    errors: List[str] = []

    for card_id in payload.card_ids:
        card = db.query(CollectionCard).filter(CollectionCard.id == card_id).first()
        if not card:
            errors.append(f"Card {card_id} not found")
            continue
        try:
            if card.game == "Magic: The Gathering":
                err = _refresh_mtg(card)
            elif card.game == "Pokémon":
                err = _refresh_pokemon(card)
            else:
                continue  # Baseball refresh not supported yet
            if err:
                errors.append(f'"{card.name}" (id {card_id}): {err}')
            else:
                updated += 1
        except Exception as e:
            errors.append(f'"{card.name}" (id {card_id}): {e}')

    db.commit()
    return {"updated": updated, "errors": errors}
