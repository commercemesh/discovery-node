"""Update embedding dimension to 1536 for OpenAI

Revision ID: 5a968e0b071d
Revises: 4d73e8079b18
Create Date: 2025-07-19 11:36:19.861660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '5a968e0b071d'
down_revision: Union[str, None] = '4d73e8079b18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old column and index
    op.execute('DROP INDEX IF EXISTS idx_products_embedding')
    op.drop_column('products', 'embedding')
    
    # Add new column with correct dimension
    op.add_column('products', sa.Column('embedding', Vector(1536), nullable=True))
    
    # Recreate index
    op.execute('CREATE INDEX idx_products_embedding ON products USING hnsw (embedding vector_cosine_ops)')


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the index
    op.execute('DROP INDEX IF EXISTS idx_products_embedding')
    
    # Drop the column
    op.drop_column('products', 'embedding')
    
    # Add back old dimension column
    op.add_column('products', sa.Column('embedding', Vector(1024), nullable=True))
    
    # Recreate index
    op.execute('CREATE INDEX idx_products_embedding ON products USING hnsw (embedding vector_cosine_ops)')
