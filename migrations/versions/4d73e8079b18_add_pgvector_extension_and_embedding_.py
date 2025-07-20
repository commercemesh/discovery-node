"""Add pgvector extension and embedding column to products

Revision ID: 4d73e8079b18
Revises: 5760b3da00ab
Create Date: 2025-07-19 09:28:56.181101

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '4d73e8079b18'
down_revision: Union[str, None] = '5760b3da00ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Add embedding column to products table
    op.add_column('products', sa.Column('embedding', Vector(1024), nullable=True))
    
    # Create index for similarity search
    op.execute('CREATE INDEX idx_products_embedding ON products USING hnsw (embedding vector_cosine_ops)')


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the index
    op.execute('DROP INDEX IF EXISTS idx_products_embedding')
    
    # Drop the column
    op.drop_column('products', 'embedding')
    
    # Note: We don't drop the extension as other tables might use it
