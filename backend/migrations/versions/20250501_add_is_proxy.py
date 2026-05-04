"""Add is_proxy column to collection_cards

Revision ID: 20250501_add_is_proxy
Revises: 20250501_add_search_preferences
Create Date: 2025-05-01 12:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250501_add_is_proxy'
down_revision = '20250501_add_search_preferences'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_proxy column to collection_cards table
    op.add_column('collection_cards', sa.Column('is_proxy', sa.Boolean(), nullable=True))


def downgrade():
    # Remove the column
    op.drop_column('collection_cards', 'is_proxy')
