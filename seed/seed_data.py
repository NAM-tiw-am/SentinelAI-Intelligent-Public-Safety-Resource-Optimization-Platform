"""
seed_data.py — Populate DB with zones, units, and sample incidents
===================================================================
Run this ONCE after creating the DB:
    python -m seed.seed_data

Zones: 10 wards of Bhopal (real centroids, mock polygons)
Units: 6 police cars + 4 ambulances spread across zones
Incidents: 20 sample incidents (mix of types/severities)

Replace with Naman's synthetic dataset generator when ready —
just make sure the zone IDs match (Z1–Z10).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models import Zone, Unit, Incident, Scenario
from app.models.unit import UnitType, UnitStatus
from app.models.incident import IncidentType, IncidentStatus
import uuid
from datetime import datetime, timedelta
import random

# ── Create tables ─────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── Zone Data — 10 Bhopal Wards ───────────────────────────────────
ZONES = [
    {
        "id": "Z1",  "name": "MG Road",
        "centroid_lat": 23.2599, "centroid_lng": 77.4126,
        "risk_score": 0.42, "area_sq_km": 4.2, "population_density": 8500,
        "polygon": [[23.255, 77.408], [23.265, 77.408], [23.265, 77.418], [23.255, 77.418]],
    },
    {
        "id": "Z2",  "name": "MP Nagar",
        "centroid_lat": 23.2350, "centroid_lng": 77.4300,
        "risk_score": 0.31, "area_sq_km": 5.1, "population_density": 7200,
        "polygon": [[23.230, 77.425], [23.240, 77.425], [23.240, 77.435], [23.230, 77.435]],
    },
    {
        "id": "Z3",  "name": "Arera Colony",
        "centroid_lat": 23.2180, "centroid_lng": 77.4450,
        "risk_score": 0.25, "area_sq_km": 6.3, "population_density": 6100,
        "polygon": [[23.213, 77.440], [23.223, 77.440], [23.223, 77.450], [23.213, 77.450]],
    },
    {
        "id": "Z4",  "name": "New Market",
        "centroid_lat": 23.2310, "centroid_lng": 77.4000,
        "risk_score": 0.61, "area_sq_km": 2.8, "population_density": 14000,
        "polygon": [[23.226, 77.395], [23.236, 77.395], [23.236, 77.405], [23.226, 77.405]],
    },
    {
        "id": "Z5",  "name": "Habibganj",
        "centroid_lat": 23.2310, "centroid_lng": 77.4380,
        "risk_score": 0.38, "area_sq_km": 3.9, "population_density": 9100,
        "polygon": [[23.226, 77.433], [23.236, 77.433], [23.236, 77.443], [23.226, 77.443]],
    },
    {
        "id": "Z6",  "name": "Shahpura",
        "centroid_lat": 23.2050, "centroid_lng": 77.4200,
        "risk_score": 0.29, "area_sq_km": 4.7, "population_density": 7600,
        "polygon": [[23.200, 77.415], [23.210, 77.415], [23.210, 77.425], [23.200, 77.425]],
    },
    {
        "id": "Z7",  "name": "Kolar Road",
        "centroid_lat": 23.1800, "centroid_lng": 77.4500,
        "risk_score": 0.22, "area_sq_km": 8.1, "population_density": 5200,
        "polygon": [[23.175, 77.445], [23.185, 77.445], [23.185, 77.455], [23.175, 77.455]],
    },
    {
        "id": "Z8",  "name": "Berasia Road",
        "centroid_lat": 23.3000, "centroid_lng": 77.3900,
        "risk_score": 0.55, "area_sq_km": 5.5, "population_density": 11200,
        "polygon": [[23.295, 77.385], [23.305, 77.385], [23.305, 77.395], [23.295, 77.395]],
    },
    {
        "id": "Z9",  "name": "Govindpura",
        "centroid_lat": 23.2700, "centroid_lng": 77.4700,
        "risk_score": 0.44, "area_sq_km": 6.8, "population_density": 8900,
        "polygon": [[23.265, 77.465], [23.275, 77.465], [23.275, 77.475], [23.265, 77.475]],
    },
    {
        "id": "Z10", "name": "Piplani",
        "centroid_lat": 23.2500, "centroid_lng": 77.4900,
        "risk_score": 0.33, "area_sq_km": 7.2, "population_density": 7000,
        "polygon": [[23.245, 77.485], [23.255, 77.485], [23.255, 77.495], [23.245, 77.495]],
    },
]

# ── Unit Data — 10 units across zones ─────────────────────────────
UNITS = [
    # Police cars
    {"id": "P01", "type": UnitType.police,    "lat": 23.2600, "lng": 77.4130, "status": UnitStatus.available, "assigned_zone": "Z1",  "call_sign": "Alpha-1"},
    {"id": "P02", "type": UnitType.police,    "lat": 23.2310, "lng": 77.4010, "status": UnitStatus.available, "assigned_zone": "Z4",  "call_sign": "Alpha-2"},
    {"id": "P03", "type": UnitType.police,    "lat": 23.3000, "lng": 77.3900, "status": UnitStatus.busy,      "assigned_zone": "Z8",  "call_sign": "Bravo-1"},
    {"id": "P04", "type": UnitType.police,    "lat": 23.2700, "lng": 77.4710, "status": UnitStatus.available, "assigned_zone": "Z9",  "call_sign": "Bravo-2"},
    {"id": "P05", "type": UnitType.police,    "lat": 23.2050, "lng": 77.4210, "status": UnitStatus.available, "assigned_zone": "Z6",  "call_sign": "Charlie-1"},
    {"id": "P06", "type": UnitType.police,    "lat": 23.1800, "lng": 77.4510, "status": UnitStatus.available, "assigned_zone": "Z7",  "call_sign": "Charlie-2"},
    # Ambulances
    {"id": "A01", "type": UnitType.ambulance, "lat": 23.2355, "lng": 77.4310, "status": UnitStatus.available, "assigned_zone": "Z2",  "call_sign": "Medic-1"},
    {"id": "A02", "type": UnitType.ambulance, "lat": 23.2185, "lng": 77.4460, "status": UnitStatus.en_route,  "assigned_zone": "Z3",  "call_sign": "Medic-2"},
    {"id": "A03", "type": UnitType.ambulance, "lat": 23.2315, "lng": 77.4390, "status": UnitStatus.available, "assigned_zone": "Z5",  "call_sign": "Medic-3"},
    {"id": "A04", "type": UnitType.ambulance, "lat": 23.2505, "lng": 77.4910, "status": UnitStatus.available, "assigned_zone": "Z10", "call_sign": "Medic-4"},
]

# ── Sample Incidents ───────────────────────────────────────────────
INCIDENT_TYPES = list(IncidentType)
ZONE_IDS = [z["id"] for z in ZONES]

def make_incidents(n: int = 20):
    now = datetime.utcnow()
    return [
        {
            "id": str(uuid.uuid4()),
            "zone_id": random.choice(ZONE_IDS),
            "type": random.choice(INCIDENT_TYPES),
            "severity": random.randint(1, 5),
            "status": random.choice([IncidentStatus.predicted, IncidentStatus.active, IncidentStatus.resolved]),
            "lat": None,
            "lng": None,
            "description": f"Sample incident #{i+1}",
            "timestamp": now - timedelta(hours=random.randint(0, 48)),
        }
        for i in range(n)
    ]


# ── Seed ──────────────────────────────────────────────────────────
def seed():
    db = SessionLocal()
    try:
        if db.query(Zone).count() > 0:
            print("DB already seeded — skipping zones/units.")
        else:
            print("Seeding zones …")
            for z in ZONES:
                db.merge(Zone(**z))

            print("Seeding units …")
            for u in UNITS:
                db.merge(Unit(**u))

            print("Seeding incidents …")
            for inc_data in make_incidents(20):
                db.add(Incident(**inc_data))

            db.commit()
            print("✓ Seed complete — 10 zones, 10 units, 20 incidents loaded.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
