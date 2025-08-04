"""rename seller_id to organization_id

Revision ID: rename_seller_to_org_id
Revises: 7cc8136a45a3
Create Date: 2025-07-30 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'rename_seller_to_org_id'
down_revision = '7cc8136a45a3'
branch_labels = None
depends_on = None


def upgrade():
    # Rename the column from seller_id to organization_id
    op.alter_column('offers', 'seller_id', new_column_name='organization_id')


def downgrade():
    # Rename the column back from organization_id to seller_id
    op.alter_column('offers', 'organization_id', new_column_name='seller_id') 