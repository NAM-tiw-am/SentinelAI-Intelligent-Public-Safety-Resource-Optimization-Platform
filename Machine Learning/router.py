"""
FastAPI router for the resource-allocation API.

Mount into your main app like this:

    from fastapi import FastAPI
    from router import router

    app = FastAPI(title="Resource Allocation API")
    app.include_router(router, prefix="/api")

Endpoints:
    GET  /health                  -> {"status": "ok"}
    GET  /zones/{zone_id}/risk    -> ZoneRiskResponse
    POST /optimize                -> list[Reassignment]
    POST /simulate                -> SimulateResponse
"""

import json, pathlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from risk_model import predict_risk
from optimizer import optimize_assignment
from routing import enrich_reassignments
from scenario_engine import run_scenario

router = APIRouter()

# ── Pydantic models ──────────────────────────────────────────────────────────

class ZoneRiskResponse(BaseModel):
    zone_id: int
    risk_score: float
    timestamp: str
    weather_condition: str


class UnitIn(BaseModel):
    id: str
    type: str                       # "police" | "ambulance"
    lat: float
    lng: float
    status: str = "available"       # "available" | "assigned"


class ZoneIn(BaseModel):
    id: int
    lat: float
    lng: float
    risk_score: float = 0.0


class OptimizeRequest(BaseModel):
    units: list[UnitIn]
    zones: list[ZoneIn]
    weather_condition: str = "clear"
    use_osrm: bool = False


class Reassignment(BaseModel):
    unit_id: str
    from_zone: int
    to_zone: int
    eta_minutes: float
    path: list[list[float]] = Field(default_factory=list)


class SimulateRequest(BaseModel):
    scenario: str                               # festival | rally | storm | multi_incident
    zone_id: Optional[int] = None               # target zone (not needed for storm)
    multi_zone_ids: Optional[list[int]] = None   # for multi_incident


class ZoneRisk(BaseModel):
    zone_id: int
    risk_score: float


class SimulateResponse(BaseModel):
    updated_risk: list[ZoneRisk]
    reassignments: list[Reassignment]


# ── State loader (stub) ─────────────────────────────────────────────────────

ROOT = pathlib.Path(__file__).parent

def load_current_state() -> tuple[list[dict], list[dict]]:
    """
    Load zones + units for simulation.

    TODO: Replace this stub with a real DB query (e.g. Postgres / Redis)
    once persistent state management is wired up.
    """
    zones = json.loads((ROOT / "zones.json").read_text())
    # Hardcoded unit roster — swap for DB lookup
    units = [
        {"id": "P1", "type": "police",    "lat": 34.060, "lng": -118.250, "status": "available"},
        {"id": "P2", "type": "police",    "lat": 34.070, "lng": -118.220, "status": "available"},
        {"id": "P3", "type": "police",    "lat": 34.050, "lng": -118.280, "status": "available"},
        {"id": "P4", "type": "police",    "lat": 34.080, "lng": -118.260, "status": "available"},
        {"id": "A1", "type": "ambulance", "lat": 34.055, "lng": -118.230, "status": "available"},
        {"id": "A2", "type": "ambulance", "lat": 34.045, "lng": -118.270, "status": "available"},
        {"id": "A3", "type": "ambulance", "lat": 34.075, "lng": -118.240, "status": "available"},
    ]
    return zones, units


# Valid zone IDs (loaded once at import for fast 404 checks)
_VALID_ZONES = {z["id"] for z in json.loads((ROOT / "zones.json").read_text())}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/zones/{zone_id}/risk", response_model=ZoneRiskResponse)
def get_zone_risk(
    zone_id: int,
    timestamp: str         = Query(default=None, description="ISO-8601 datetime, defaults to now"),
    weather_condition: str = Query(default="clear"),
    is_event_day: bool     = Query(default=False),
    expected_crowd_size: int = Query(default=0),
):
    try:
        if zone_id not in _VALID_ZONES:
            raise HTTPException(404, f"Zone {zone_id} not found")

        ts = datetime.fromisoformat(timestamp) if timestamp else datetime.now()
        score = predict_risk(zone_id, ts, weather_condition,
                             is_event_day, expected_crowd_size)

        return ZoneRiskResponse(zone_id=zone_id, risk_score=round(score, 4),
                                timestamp=ts.isoformat(),
                                weather_condition=weather_condition)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Internal error: {e}")


@router.post("/optimize", response_model=list[Reassignment])
def post_optimize(req: OptimizeRequest):
    try:
        units = [u.model_dump() for u in req.units]
        zones = [z.model_dump() for z in req.zones]

        raw = optimize_assignment(units, zones)
        enriched = enrich_reassignments(raw, units, zones,
                                        req.weather_condition, req.use_osrm)
        return [Reassignment(**r) for r in enriched]
    except Exception as e:
        raise HTTPException(500, f"Internal error: {e}")


@router.post("/simulate", response_model=SimulateResponse)
def post_simulate(req: SimulateRequest):
    try:
        zones, units = load_current_state()
        result = run_scenario(
            scenario=req.scenario,
            zone_id=req.zone_id,
            zones=zones,
            units=units,
            multi_zone_ids=req.multi_zone_ids,
        )
        return SimulateResponse(
            updated_risk=[ZoneRisk(**r) for r in result["updated_risk"]],
            reassignments=[Reassignment(**r) for r in result["reassignments"]],
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Internal error: {e}")
