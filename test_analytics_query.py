#!/usr/bin/env python3
"""Test the analytics query directly"""
import os
from sqlalchemy import create_engine, text
from datetime import datetime, date, time
import pytz

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/cmp_discovery")
engine = create_engine(DATABASE_URL)

# Simulate what the analytics service is doing
tz = "America/Los_Angeles"
timezone_obj = pytz.timezone(tz)
now_in_tz = datetime.now(timezone_obj)
from_date = now_in_tz.date()
to_date = now_in_tz.date()

# Create datetime bounds
start_datetime = timezone_obj.localize(datetime.combine(from_date, time.min))
end_datetime = timezone_obj.localize(datetime.combine(to_date, time.max))

print(f"Timezone: {tz}")
print(f"From date: {from_date}")
print(f"To date: {to_date}")
print(f"Start datetime: {start_datetime}")
print(f"End datetime: {end_datetime}")
print(f"Start (no tz): {start_datetime.replace(tzinfo=None)}")
print(f"End (no tz): {end_datetime.replace(tzinfo=None)}")

with engine.connect() as conn:
    # Test the query that's failing
    query = text(f"""
        SELECT COUNT(*) as count
        FROM api_usage_metrics
        WHERE api_usage_metrics.timestamp AT TIME ZONE 'UTC' AT TIME ZONE '{tz}' 
        BETWEEN :start_time AND :end_time
    """)
    
    result = conn.execute(query, {
        "start_time": start_datetime.replace(tzinfo=None),
        "end_time": end_datetime.replace(tzinfo=None)
    })
    count = result.scalar()
    print(f"\nQuery result: {count}")
    
    # Test your working query
    working_query = text("""
        SELECT COUNT(*) as count
        FROM api_usage_metrics
        WHERE timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Los_Angeles' >= NOW() AT TIME ZONE 'America/Los_Angeles'
    """)
    result = conn.execute(working_query)
    print(f"Your working query result: {result.scalar()}")
    
    # Debug: show some sample conversions
    debug_query = text("""
        SELECT 
            timestamp,
            timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Los_Angeles' as converted_time
        FROM api_usage_metrics
        LIMIT 5
    """)
    result = conn.execute(debug_query)
    print("\nSample timestamp conversions:")
    for row in result:
        print(f"  {row.timestamp} -> {row.converted_time}")