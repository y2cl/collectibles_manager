"""Add rich MTG data fields for Cube Maker sync

Revision ID: 20250428_add_mtg_rich_fields
Revises: previous_revision
Create Date: 2025-04-28 15:45:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250428_add_mtg_rich_fields'
down_revision = None  # Update this to point to your previous migration
branch_labels = None
depends_on = None


def upgrade():
    # Add rich MTG data fields to collection_cards table
    op.add_column('collection_cards', sa.Column('scryfall_id', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('mana_cost', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('type_line', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('oracle_text', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('keywords', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('power', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('toughness', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('rarity', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('color_identity', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('finish', sa.String(), nullable=True))
    op.add_column('collection_cards', sa.Column('tcg_link', sa.String(), nullable=True))
    
    # Create index on scryfall_id for faster lookups
    op.create_index('ix_collection_cards_scryfall_id', 'collection_cards', ['scryfall_id'])


def downgrade():
    # Remove the columns
    op.drop_index('ix_collection_cards_scryfall_id', table_name='collection_cards')
    op.drop_column('collection_cards', 'tcg_link')
    op.drop_column('collection_cards', 'finish')
    op.drop_column('collection_cards', 'color_identity')
    op.drop_column('collection_cards', 'rarity')
    op.drop_column('collection_cards', 'toughness')
    op.drop_column('collection_cards', 'power')
    op.drop_column('collection_cards', 'keywords')
    op.drop_column('collection_cards', 'oracle_text')
    op.drop_column('collection_cards', 'type_line')
    op.drop_column('collection_cards', 'mana_cost')
    op.drop_column('collection_cards', 'scryfall_id')
