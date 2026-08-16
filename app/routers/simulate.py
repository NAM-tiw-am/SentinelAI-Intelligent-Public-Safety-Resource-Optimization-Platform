"""
simulate.py router — Scenario Simulator (wired to Naman's scenario_engine)
===========================================================================
POST /simulate { "scenario": "festival", "zone_id": "Z4" }

Flow:
  1. Load zones + units from DB
  2. Translate zone IDs (str → int) for Naman's engine
  3. Call Naman's run_scenario() — spikes risk + runs OR-Tools + enriches routes
  4. Translate results back (int → str zone IDs)
  5. Persist spiked risk + new assignments to DB
  6. Broadcast via WebSocket (risk_updated + unit_reassigned)
  7. Save Scenario audit record
  8. Return SimulateResponse
"""

from __future__ import annotations
import app.ml  # ← path bridge (must be first)

import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.zone import Zone
from app.models.unit import Unit, UnitStatus
from app.models.scenario import Scenario
from app.schemas.simulate import SimulateRequest, SimulateResponse, RiskUpdate, Reassignment
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/simulate", tags=["Scenario Simulator"])

# Naman's scenario engine — graceful fallback if OR-Tools DLL fails
_SCENARIO_OK = False
try:
    from scenario_engine import run_scenario as _run_scenario
    _SCENARIO_OK = True
    logger.info("Naman's scenario_engine loaded")
except Exception as e:
    logger.warning(f"scenario_engine unavailable — using local simulate logic: {e}")

# Zone ID maps
STR_TO_INT: dict[str, int] = {
    "Z1": 0, "Z2": 1, "Z3": 2,  "Z4": 3,  "Z5": 4,
    "Z6": 5, "Z7": 6, "Z8": 7,  "Z9": 8,  "Z10": 9,
}
INT_TO_STR: dict[int, str] = {v: k for k, v in STR_TO_INT.items()}


def _map_status(s) -> str:
    s = s if isinstance(s, str) else s.value
    return "assigned" if s in ("busy", "en_route") else "available"


@router.post("/", response_model=SimulateResponse, summary="Run a scenario simulation")
async def simulate(payload: SimulateRequest, db: Session = Depends(get_db)):
    """
    Triggers Naman's scenario engine, persists results to DB,
    and broadcasts live WebSocket events to the frontend.
    """
    all_zones = db.query(Zone).all()
    all_units = db.query(Unit).all()

    if not all_zones:
        raise HTTPException(status_code=404, detail="No zones in DB — run seed_data.py first")

    # ── 1. Build Naman-format zone + unit lists ────────────────────
    naman_zones = [
        {
            "id":         STR_TO_INT.get(z.id, 0),
            "lat":        z.centroid_lat,
            "lng":        z.centroid_lng,
            "risk_score": z.risk_score,
        }
        for z in all_zones
    ]

    naman_units = [
        {
            "id":     u.id,
            "type":   u.type if isinstance(u.type, str) else u.type.value,
            "lat":    u.lat,
            "lng":    u.lng,
            "status": _map_status(u.status),
        }
        for u in all_units
    ]

    # ── 2. Translate zone_id str → int for Naman ──────────────────
    naman_zone_id: int | None = None
    if payload.zone_id:
        naman_zone_id = STR_TO_INT.get(payload.zone_id)
        if naman_zone_id is None:
            raise HTTPException(status_code=400, detail=f"Unknown zone_id: {payload.zone_id}")

    # ── 3. Run Naman's scenario engine ────────────────────────────
    try:
        result = _run_scenario(
            scenario=payload.scenario.value,
            zone_id=naman_zone_id,
            zones=naman_zones,
            units=naman_units,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Scenario engine error: {e}")
        raise HTTPException(status_code=500, detail=f"Scenario engine error: {e}")

    # ── 4. Translate results back: int IDs → str IDs ──────────────
    updated_risk = [
        RiskUpdate(
            zone_id=INT_TO_STR.get(r["zone_id"], f"Z{r['zone_id']+1}"),
            risk_score=round(float(r["risk_score"]), 4),
        )
        for r in result["updated_risk"]
    ]

    reassignments = [
        Reassignment(
            unit_id=r["unit_id"],
            from_zone=INT_TO_STR.get(r.get("from_zone"), None),
            to_zone=INT_TO_STR.get(r["to_zone"], "Z1"),
            eta_minutes=round(float(r.get("eta_minutes", 0.0)), 1),
            route=r.get("path", []),
        )
        for r in result["reassignments"]
    ]

    # ── 5. Persist spiked risk + new unit assignments to DB ────────
    risk_map = {r.zone_id: r.risk_score for r in updated_risk}
    for zone in all_zones:
        if zone.id in risk_map:
            zone.risk_score = risk_map[zone.id]

    unit_map = {u.id: u for u in all_units}
    for r in reassignments:
        unit = unit_map.get(r.unit_id)
        if unit:
            unit.assigned_zone = r.to_zone
            unit.status = UnitStatus.en_route

    # ── 6. Save audit record ───────────────────────────────────────
    scenario_record = Scenario(
        id=str(uuid.uuid4()),
        name=payload.scenario,
        zone_id=payload.zone_id,
        risk_multiplier=1.0,   # Naman's engine handles multipliers internally
        affected_zones=[r.zone_id for r in updated_risk if r.risk_score > 0.6],
        result_snapshot={
            "updated_risk":   [r.model_dump() for r in updated_risk],
            "reassignments":  [r.model_dump() for r in reassignments],
        },
    )
    db.add(scenario_record)
    db.commit()

    # ── 7. Broadcast via WebSocket ────────────────────────────────
    await ws_manager.broadcast("risk_updated", {
        "scenario": payload.scenario,
        "updated_risk": [r.model_dump() for r in updated_risk],
    })
    await ws_manager.broadcast("unit_reassigned", {
        "scenario": payload.scenario,
        "reassignments": [r.model_dump() for r in reassignments],
    })

    # ── 8. Dashboard KPIs ─────────────────────────────────────────
    covered = {r.to_zone for r in reassignments}
    coverage_pct = round(len(covered) / max(len(all_zones), 1) * 100, 1)
    avg_eta = (
        round(sum(r.eta_minutes for r in reassignments) / len(reassignments), 1)
        if reassignments else 0.0
    )

    return SimulateResponse(
        scenario_id=scenario_record.id,
        scenario=payload.scenario,
        updated_risk=updated_risk,
        reassignments=reassignments,
        coverage_pct=coverage_pct,
        avg_response_time_minutes=avg_eta,
    )
