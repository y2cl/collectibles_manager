"""Add search UI preferences to app_settings

Revision ID: 20250501_add_search_preferences
Revises: 20250428_add_mtg_rich_fields
Create Date: 2025-05-01 11:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250501_add_search_preferences'
down_revision = '20250428_add_mtg_rich_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add search preferences columns to app_settings table
    op.add_column('app_settings', sa.Column('search_cards_per_row', sa.Integer(), nullable=True))
    op.add_column('app_settings', sa.Column('search_sort_by', sa.String(), nullable=True))


def downgrade():
    # Remove the columns
    op.drop_column('app_settings', 'search_sort_by')
    op.drop_column('app_settings', 'search_cards_per_row')
