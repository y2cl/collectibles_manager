"""
SportsCardSet ORM model — user-defined catalog of Sports Card sets/inserts.
Separate from the collection_cards table; stores set metadata (card count, link, notes).
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Index
from ..database import Base


class SportsCardSet(Base):
    __tablename__ = "sports_card_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    profile_id = Column(String, nullable=False, default="default")

    sport = Column(String, nullable=True)       # "baseball" | "football" | etc.
    set_name = Column(String, nullable=False)
    insert_name = Column(String, default="")    # blank = base set; non-blank = named insert
    year = Column(String, default="")
    card_count = Column(Integer, nullable=True)  # total cards in the set/insert
    link = Column(String, default="")            # URL to external info
    notes = Column(String, default="")

    __table_args__ = (
        Index("ix_scs_owner_profile", "owner_id", "profile_id"),
    )
