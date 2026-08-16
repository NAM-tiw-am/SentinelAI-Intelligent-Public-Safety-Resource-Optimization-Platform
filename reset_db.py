"""
reset_db.py — Drop all SentinelAI tables and recreate them fresh.
Run this ONCE when you hit schema mismatch errors:
    python reset_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.models import Zone, Unit, Incident, Scenario   # registers all models

print("Dropping all SentinelAI tables ...")
Base.metadata.drop_all(bind=engine)
print("Recreating tables with correct schema ...")
Base.metadata.create_all(bind=engine)
print("Done - tables recreated. Now run: python -m seed.seed_data")
