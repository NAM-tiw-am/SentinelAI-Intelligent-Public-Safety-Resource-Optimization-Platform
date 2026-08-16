from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.incident import Incident, IncidentStatus
from app.schemas.incident import IncidentOut, IncidentCreate
from app.websocket.manager import ws_manager
import uuid
from datetime import datetime

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("/", response_model=list[IncidentOut], summary="List incidents")
def list_incidents(
    status: str | None = Query(None, description="Filter by status: predicted|active|resolved"),
    zone_id: str | None = Query(None, description="Filter by zone"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status)
    if zone_id:
        query = query.filter(Incident.zone_id == zone_id)
    return query.order_by(Incident.timestamp.desc()).limit(limit).all()


@router.get("/{incident_id}", response_model=IncidentOut, summary="Get a single incident")
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@router.post("/", response_model=IncidentOut, status_code=201, summary="Report a new incident")
async def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    incident = Incident(
        id=str(uuid.uuid4()),
        timestamp=payload.timestamp or datetime.utcnow(),
        **payload.model_dump(exclude={"timestamp"}),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # Push live to all connected WebSocket clients
    await ws_manager.broadcast("incident_created", {
        "id": incident.id,
        "zone_id": incident.zone_id,
        "type": incident.type,
        "severity": incident.severity,
        "status": incident.status,
        "lat": incident.lat,
        "lng": incident.lng,
    })
    return incident


@router.patch("/{incident_id}/status", response_model=IncidentOut, summary="Update incident status")
def update_incident_status(
    incident_id: str,
    status: IncidentStatus,
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    inc.status = status
    db.commit()
    db.refresh(inc)
    return inc
