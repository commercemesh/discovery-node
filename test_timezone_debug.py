#!/usr/bin/env python3
"""Debug timezone issue with analytics API"""
import os
from sqlalchemy import create_engine, text
from datetime import datetime, date, time
import pytz

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/cmp_discovery")

# Create engine
engine = create_engine(DATABASE_URL)

# Test queries
with engine.connect() as conn:
    # 1. Total count
    result = conn.execute(text("SELECT COUNT(*) as total FROM api_usage_metrics"))
    total = result.scalar()
    print(f"Total records: {total}")
    
    # 2. Count by date
    result = conn.execute(text("""
        SELECT DATE(timestamp) as date, COUNT(*) as count 
        FROM api_usage_metrics 
        GROUP BY DATE(timestamp) 
        ORDER BY date
    """))
    print("\nRecords by date:")
    for row in result:
        print(f"  {row.date}: {row.count}")
    
    # 3. Test timezone-aware query for today in PST
    tz = pytz.timezone('America/Los_Angeles')
    today = datetime.now(tz).date()
    start = tz.localize(datetime.combine(today, time.min))
    end = tz.localize(datetime.combine(today, time.max))
    
    print(f"\nQuerying for today ({today}) in PST:")
    print(f"  Start: {start}")
    print(f"  End: {end}")
    
    # Try the query
    result = conn.execute(
        text("SELECT COUNT(*) FROM api_usage_metrics WHERE timestamp >= :start AND timestamp <= :end"),
        {"start": start, "end": end}
    )
    count = result.scalar()
    print(f"  Result: {count} records")
    
    # 4. Show a few sample timestamps
    result = conn.execute(text("SELECT timestamp FROM api_usage_metrics LIMIT 5"))
    print("\nSample timestamps:")
    for row in result:
        print(f"  {row.timestamp}")