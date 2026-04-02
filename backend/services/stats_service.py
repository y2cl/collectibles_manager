"""
Collection statistics and investment analysis.
Returns raw aggregated data for the frontend to render charts.
Ported from collectiman.py::render_investment_tab — no Streamlit/pandas dependencies.
"""
from typing import List, Dict
from sqlalchemy.orm import Session


def get_collection_stats(db: Session, owner_db_id: int, profile_id: str, game: str = None) -> Dict:
    """
    Returns aggregated stats for the investment tab:
    - value_by_game: [{game, total_value}]
    - top_sets: [{set_label, total_value}] top 15
    - paid_vs_market: {total_paid, total_market}
    """
    from ..models.card import CollectionCard

    q = db.query(CollectionCard).filter(
        CollectionCard.owner_id == owner_db_id,
        CollectionCard.profile_id == profile_id,
    )
    if game:
        q = q.filter(CollectionCard.game == game)
    cards = q.all()

    if not cards:
        return {
            "value_by_game": [],
            "top_sets": [],
            "paid_vs_market": {"total_paid": 0.0, "total_market": 0.0},
        }

    # Value by game
    game_totals: Dict[str, float] = {}
    for c in cards:
        g = c.game or "Unknown"
        game_totals[g] = game_totals.get(g, 0.0) + (c.price_usd or 0.0) * (c.quantity or 1)
    value_by_game = [
        {"game": g, "total_value": round(v, 2)}
        for g, v in sorted(game_totals.items(), key=lambda x: -x[1])
    ]

    # Top sets by value
    set_totals: Dict[str, float] = {}
    for c in cards:
        label = f"{c.year} {c.set_name}".strip() or "Unknown Set"
        set_totals[label] = set_totals.get(label, 0.0) + (c.price_usd or 0.0) * (c.quantity or 1)
    top_sets = [
        {"set_label": s, "total_value": round(v, 2)}
        for s, v in sorted(set_totals.items(), key=lambda x: -x[1])[:15]
    ]

    # Paid vs market
    total_paid = sum((c.paid or 0.0) for c in cards)
    total_market = sum((c.price_usd or 0.0) * (c.quantity or 1) for c in cards)

    return {
        "value_by_game": value_by_game,
        "top_sets": top_sets,
        "paid_vs_market": {
            "total_paid": round(total_paid, 2),
            "total_market": round(total_market, 2),
        },
    }
