from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from app.database import get_db
from app.models.zone import Zone
from app.models.unit import Unit, UnitStatus
from app.models.scenario import Scenario
from app.schemas.simulate import SimulateRequest, SimulateResponse, RiskUpdate, Reassignment
from app.services.optimizer import run_optimizer
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/simulate", tags=["Scenario Simulator"])

# Per-scenario risk spike config:
# Which zone IDs are affected and their risk multiplier / affected radius
SCENARIO_CONFIG: dict[str, dict] = {
    "festival": {
        "radius": 2,             # affects epicentre + 2 neighbouring zones
        "risk_multiplier": 1.6,
        "description": "Large public gathering — elevated crowd control & medical risk",
    },
    "rally": {
        "radius": 1,
        "risk_multiplier": 1.8,
        "description": "Political rally — very high crowd control risk",
    },
    "storm": {
        "radius": 99,            # affects all zones
        "risk_multiplier": 1.4,
        "description": "Weather event — elevated accident & medical risk city-wide",
    },
    "multi_incident": {
        "radius": 3,
        "risk_multiplier": 2.0,
        "description": "Multiple simultaneous incidents — max resource demand",
    },
}


def _spike_risk(current: float, multiplier: float) -> float:
    return round(min(current * multiplier + 0.1, 1.0), 4)


@router.post("/", response_model=SimulateResponse, summary="Run a scenario simulation")
async def simulate(payload: SimulateRequest, db: Session = Depends(get_db)):
    """
    POST /simulate { "scenario": "festival", "zone_id": "Z1" }

    1. Spikes risk scores for zones affected by the scenario
    2. Runs the optimizer on spiked scores
    3. Persists updated unit assignments
    4. Broadcasts risk_updated + unit_reassigned via WebSocket
    5. Saves a Scenario record for audit / replay

    This is the DEMO CENTREPIECE — keep it fast (<200ms target).
    """
    config = SCENARIO_CONFIG.get(payload.scenario.value)
    if not config:
        raise HTTPException(status_code=400, detail="Unknown scenario type")

    all_zones = db.query(Zone).all()
    all_units = db.query(Unit).all()

    # ── 1. Determine affected zones ────────────────────────────────
    epicentre = None
    if payload.zone_id:
        epicentre = next((z for z in all_zones if z.id == payload.zone_id), None)

    # Simple heuristic: affect epicentre + first N zones by zone index
    # Naman can replace with actual geographic adjacency from PostGIS
    affected_ids: set[str] = set()
    radius = config["radius"]

    if epicentre:
        affected_ids.add(epicentre.id)
        # Add up to `radius` neighbouring zones (by zone list order as proxy)
        for z in all_zones:
            if len(affected_ids) >= radius + 1:
                break
            affected_ids.add(z.id)
    else:
        # No epicentre → affect all
        affected_ids = {z.id for z in all_zones}

    # ── 2. Spike risk scores (in memory only — don't commit yet) ───
    multiplier = config["risk_multiplier"]
    updated_risk: list[RiskUpdate] = []
    zone_dicts_spiked = []

    for zone in all_zones:
        if zone.id in affected_ids:
            spiked = _spike_risk(zone.risk_score, multiplier)
        else:
            spiked = zone.risk_score

        updated_risk.append(RiskUpdate(zone_id=zone.id, risk_score=spiked))
        zone_dicts_spiked.append({
            "id": zone.id,
            "centroid_lat": zone.centroid_lat,
            "centroid_lng": zone.centroid_lng,
            "risk_score": spiked,
        })

    # ── 3. Run optimizer on spiked scores ─────────────────────────
    unit_dicts = [
        {
            "id": u.id,
            "type": u.type,
            "lat": u.lat,
            "lng": u.lng,
            "status": u.status,
            "assigned_zone": u.assigned_zone,
        }
        for u in all_units
    ]
    raw_reassignments = run_optimizer(zone_dicts_spiked, unit_dicts, risk_threshold=0.5)
    reassignments = [Reassignment(**r) for r in raw_reassignments]

    # ── 4. Persist spiked risk + new assignments to DB ─────────────
    risk_map = {r.zone_id: r.risk_score for r in updated_risk}
    for zone in all_zones:
        zone.risk_score = risk_map[zone.id]

    unit_map = {u.id: u for u in all_units}
    for r in reassignments:
        unit = unit_map.get(r.unit_id)
        if unit:
            unit.assigned_zone = r.to_zone
            unit.status = UnitStatus.en_route

    # ── 5. Save scenario audit record ─────────────────────────────
    scenario_record = Scenario(
        id=str(uuid.uuid4()),
        name=payload.scenario,
        zone_id=payload.zone_id,
        risk_multiplier=multiplier,
        affected_zones=list(affected_ids),
        result_snapshot={
            "updated_risk": [r.model_dump() for r in updated_risk],
            "reassignments": [r.model_dump() for r in reassignments],
        },
    )
    db.add(scenario_record)
    db.commit()

    # ── 6. Broadcast via WebSocket ─────────────────────────────────
    await ws_manager.broadcast("risk_updated", {
        "scenario": payload.scenario,
        "updated_risk": [r.model_dump() for r in updated_risk],
    })
    await ws_manager.broadcast("unit_reassigned", {
        "scenario": payload.scenario,
        "reassignments": [r.model_dump() for r in reassignments],
    })

    # Quick coverage & ETA stats for the dashboard
    covered_zones = {r.to_zone for r in reassignments}
    coverage_pct = round(len(covered_zones) / max(len(all_zones), 1) * 100, 1)
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
