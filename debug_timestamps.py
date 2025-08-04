#!/usr/bin/env python3
"""Debug timestamp storage and retrieval"""
import os
from sqlalchemy import create_engine, text
from datetime import datetime
import pytz

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/cmp_discovery")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Get current database time and timezone
    result = conn.execute(text("""
        SELECT 
            NOW() as current_db_time,
            current_setting('TIMEZONE') as db_timezone,
            NOW() AT TIME ZONE 'UTC' as current_utc,
            NOW() AT TIME ZONE 'America/Los_Angeles' as current_pst
    """))
    row = result.fetchone()
    print("Database Info:")
    print(f"  Current DB Time: {row.current_db_time}")
    print(f"  DB Timezone: {row.db_timezone}")
    print(f"  Current UTC: {row.current_utc}")
    print(f"  Current PST: {row.current_pst}")
    
    # Check how dates are interpreted
    print("\nDate interpretation test:")
    result = conn.execute(text("""
        SELECT 
            COUNT(*) as count,
            DATE(timestamp) as date_part,
            DATE(timestamp AT TIME ZONE 'UTC') as date_utc,
            DATE(timestamp AT TIME ZONE 'America/Los_Angeles') as date_pst,
            MIN(timestamp) as earliest,
            MAX(timestamp) as latest
        FROM api_usage_metrics
        GROUP BY DATE(timestamp), DATE(timestamp AT TIME ZONE 'UTC'), DATE(timestamp AT TIME ZONE 'America/Los_Angeles')
        ORDER BY date_part
    """))
    
    for row in result:
        print(f"\n  Count: {row.count}")
        print(f"  DATE(timestamp): {row.date_part}")
        print(f"  DATE(... AT TIME ZONE 'UTC'): {row.date_utc}")
        print(f"  DATE(... AT TIME ZONE 'PST'): {row.date_pst}")
        print(f"  Earliest: {row.earliest}")
        print(f"  Latest: {row.latest}")
    
    # Python timezone check
    print("\nPython timezone check:")
    pst = pytz.timezone('America/Los_Angeles')
    now_pst = datetime.now(pst)
    print(f"  Python now PST: {now_pst}")
    print(f"  Python today PST: {now_pst.date()}")