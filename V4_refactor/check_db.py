#!/usr/bin/env python3
"""Simple database inspection script for MicroTutor V4."""

import sys
import os
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config.config import config
import asyncpg

async def inspect_database():
    """Inspect the database and show tables and data."""
    try:
        print("🔗 Connecting to database...")
        print(f"   URL: {config.database_url[:50]}...")
        
        # Try different SSL modes
        ssl_modes = ['require', 'prefer', 'disable']
        
        for ssl_mode in ssl_modes:
            try:
                print(f"   Trying SSL mode: {ssl_mode}")
                conn = await asyncpg.connect(config.database_url, ssl=ssl_mode)
                print(f"   ✅ Connected with SSL mode: {ssl_mode}")
                break
            except Exception as e:
                print(f"   ❌ Failed with SSL mode {ssl_mode}: {e}")
                if ssl_mode == ssl_modes[-1]:
                    raise e
                continue
        
        # Get all tables
        print("\n📊 Database Tables:")
        tables = await conn.fetch("""
            SELECT table_name, table_type
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        if not tables:
            print("   No tables found in public schema")
        else:
            for table in tables:
                print(f"   - {table['table_name']} ({table['table_type']})")
        
        # Check data in each table
        print("\n📈 Table Data Counts:")
        for table in tables:
            try:
                count = await conn.fetchval(f'SELECT COUNT(*) FROM "{table["table_name"]}"')
                print(f"   📊 {table['table_name']}: {count} rows")
                
                # Show sample data for tables with data
                if count > 0 and count <= 10:
                    sample = await conn.fetch(f'SELECT * FROM "{table["table_name"]}" LIMIT 3')
                    print(f"      Sample data:")
                    for row in sample:
                        print(f"        {dict(row)}")
                elif count > 10:
                    sample = await conn.fetch(f'SELECT * FROM "{table["table_name"]}" LIMIT 3')
                    print(f"      Sample data (first 3 rows):")
                    for row in sample:
                        print(f"        {dict(row)}")
                        
            except Exception as e:
                print(f"   ❌ Error reading {table['table_name']}: {e}")
        
        # Check for specific MicroTutor tables
        print("\n🔍 Looking for MicroTutor-specific tables:")
        microtutor_tables = [
            'cases', 'conversations', 'feedback', 'users', 'sessions',
            'tutor_responses', 'patient_responses', 'case_generations'
        ]
        
        for table_name in microtutor_tables:
            try:
                exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = $1
                    )
                """, table_name)
                if exists:
                    count = await conn.fetchval(f'SELECT COUNT(*) FROM "{table_name}"')
                    print(f"   ✅ {table_name}: {count} rows")
                else:
                    print(f"   ❌ {table_name}: not found")
            except Exception as e:
                print(f"   ❌ Error checking {table_name}: {e}")
        
        await conn.close()
        print("\n✅ Database inspection complete!")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        print(f"   Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(inspect_database())
