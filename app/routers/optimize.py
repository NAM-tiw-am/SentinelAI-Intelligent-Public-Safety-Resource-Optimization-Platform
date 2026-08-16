from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.zone import Zone
from app.models.unit import Unit, UnitStatus
from app.services.optimizer import run_optimizer
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/optimize", tags=["Optimizer"])


@router.post("/", summary="Run optimizer — reassign units based on current risk scores")
async def optimize(
    risk_threshold: float = 0.6,
    db: Session = Depends(get_db),
):
    """
    Reads current zone risk scores + unit positions from DB,
    runs the allocation optimizer, persists new assignments,
    and broadcasts reassignments via WebSocket.
    """
    zones = db.query(Zone).all()
    units = db.query(Unit).all()

    zone_dicts = [
        {
            "id": z.id,
            "centroid_lat": z.centroid_lat,
            "centroid_lng": z.centroid_lng,
            "risk_score": z.risk_score,
        }
        for z in zones
    ]
    unit_dicts = [
        {
            "id": u.id,
            "type": u.type,
            "lat": u.lat,
            "lng": u.lng,
            "status": u.status,
            "assigned_zone": u.assigned_zone,
        }
        for u in units
    ]

    reassignments = run_optimizer(zone_dicts, unit_dicts, risk_threshold)

    # Persist new assignments to DB
    unit_map = {u.id: u for u in units}
    for r in reassignments:
        unit = unit_map.get(r["unit_id"])
        if unit:
            unit.assigned_zone = r["to_zone"]
            unit.status = UnitStatus.en_route

    db.commit()

    # Push live to all connected WebSocket clients
    await ws_manager.broadcast("unit_reassigned", {"reassignments": reassignments})

    return {"reassignments": reassignments, "count": len(reassignments)}
