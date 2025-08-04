#!/usr/bin/env python3
"""Check and setup multi-tenant configuration."""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cmp_discovery")

def check_setup():
    """Check current multi-tenant setup."""
    print("🔍 Checking multi-tenant setup...")
    print(f"Database: {DATABASE_URL}")
    print(f"Multi-tenant mode: {os.getenv('MULTI_TENANT_MODE', 'false')}")
    print()
    
    try:
        # Connect to database
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if subdomain column exists
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'organizations' 
            AND column_name = 'subdomain'
        """)).fetchone()
        
        if not result:
            print("❌ Subdomain column not found. Run: alembic upgrade head")
            return False
        
        print("✅ Subdomain column exists")
        
        # List organizations and their subdomains
        orgs = session.execute(text("""
            SELECT id, name, subdomain 
            FROM organizations 
            ORDER BY name
        """)).fetchall()
        
        print(f"\n📋 Found {len(orgs)} organizations:")
        for org in orgs:
            subdomain_status = "✅" if org.subdomain else "❌ Missing"
            print(f"   - {org.name}: {org.subdomain or 'None'} {subdomain_status}")
            
        # Check for products
        product_counts = session.execute(text("""
            SELECT o.name, COUNT(p.id) as product_count
            FROM organizations o
            LEFT JOIN products p ON p.organization_id = o.id
            GROUP BY o.id, o.name
            ORDER BY o.name
        """)).fetchall()
        
        print("\n📦 Product counts by organization:")
        for org_name, count in product_counts:
            print(f"   - {org_name}: {count} products")
        
        # Suggest test URLs
        print("\n🌐 Test URLs (after adding to /etc/hosts):")
        for org in orgs:
            if org.subdomain:
                print(f"   - http://{org.subdomain}.localhost:8000/api/v1/search?q=test")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def update_missing_subdomains():
    """Update organizations with missing subdomains."""
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Find organizations without subdomains
        orgs = session.execute(text("""
            SELECT id, name 
            FROM organizations 
            WHERE subdomain IS NULL OR subdomain = ''
        """)).fetchall()
        
        if orgs:
            print(f"\n🔧 Updating {len(orgs)} organizations with missing subdomains...")
            
            for org_id, org_name in orgs:
                # Generate subdomain from name
                import re
                subdomain = org_name.lower()
                subdomain = re.sub(r'[^a-z0-9]+', '-', subdomain)
                subdomain = subdomain.strip('-')[:63]
                
                # Ensure uniqueness
                counter = 0
                base_subdomain = subdomain
                while True:
                    check = session.execute(text(
                        "SELECT 1 FROM organizations WHERE subdomain = :subdomain AND id != :id"
                    ), {"subdomain": subdomain, "id": org_id}).fetchone()
                    
                    if not check:
                        break
                    counter += 1
                    subdomain = f"{base_subdomain}-{counter}"
                
                # Update organization
                session.execute(text(
                    "UPDATE organizations SET subdomain = :subdomain WHERE id = :id"
                ), {"subdomain": subdomain, "id": org_id})
                
                print(f"   ✅ {org_name} → {subdomain}")
            
            session.commit()
            print("   Done!")
        
        session.close()
        
    except Exception as e:
        print(f"❌ Error updating subdomains: {e}")

if __name__ == "__main__":
    if check_setup():
        print("\n✅ Multi-tenant setup looks good!")
        
        # Check if we need to update subdomains
        if "--update-subdomains" in sys.argv:
            update_missing_subdomains()
    else:
        print("\n❌ Setup incomplete. Please fix the issues above.")
        sys.exit(1)