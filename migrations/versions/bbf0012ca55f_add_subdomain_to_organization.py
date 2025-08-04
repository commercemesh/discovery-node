"""add_subdomain_to_organization

Revision ID: bbf0012ca55f
Revises: 5a968e0b071d
Create Date: 2025-07-27 13:10:49.023541

"""
from typing import Sequence, Union
import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'bbf0012ca55f'
down_revision: Union[str, None] = '5a968e0b071d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def generate_subdomain(name: str) -> str:
    """Generate a URL-safe subdomain from organization name."""
    # Convert to lowercase
    subdomain = name.lower()
    
    # Replace spaces and special characters with hyphens
    subdomain = re.sub(r'[^a-z0-9]+', '-', subdomain)
    
    # Remove leading/trailing hyphens
    subdomain = subdomain.strip('-')
    
    # Ensure it starts with a letter (prepend 'org-' if it doesn't)
    if subdomain and not subdomain[0].isalpha():
        subdomain = f'org-{subdomain}'
    
    # Limit length to 63 characters (DNS subdomain limit)
    subdomain = subdomain[:63]
    
    return subdomain


def upgrade() -> None:
    """Add subdomain column to organizations table and populate with generated values."""
    # Add subdomain column (initially nullable)
    op.add_column('organizations', 
        sa.Column('subdomain', sa.String(), nullable=True, comment='Unique subdomain for multi-tenant access')
    )
    
    # Create index on subdomain
    op.create_index('idx_organizations_subdomain', 'organizations', ['subdomain'], unique=True)
    
    # Populate subdomain for existing organizations
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT id, name FROM organizations"))
    
    for row in result:
        org_id = row.id
        org_name = row.name
        base_subdomain = generate_subdomain(org_name)
        subdomain = base_subdomain
        
        # Handle duplicates by appending numbers
        counter = 1
        while True:
            # Check if subdomain already exists
            exists = connection.execute(
                sa.text("SELECT 1 FROM organizations WHERE subdomain = :subdomain AND id != :id"),
                {"subdomain": subdomain, "id": org_id}
            ).fetchone()
            
            if not exists:
                break
                
            counter += 1
            subdomain = f"{base_subdomain}-{counter}"
        
        # Update the organization with the generated subdomain
        connection.execute(
            sa.text("UPDATE organizations SET subdomain = :subdomain WHERE id = :id"),
            {"subdomain": subdomain, "id": org_id}
        )
    
    # Make subdomain column non-nullable for future inserts
    # (existing records now have values)
    op.alter_column('organizations', 'subdomain', nullable=False)


def downgrade() -> None:
    """Remove subdomain column from organizations table."""
    # Drop the index first
    op.drop_index('idx_organizations_subdomain', table_name='organizations')
    
    # Drop the column
    op.drop_column('organizations', 'subdomain')