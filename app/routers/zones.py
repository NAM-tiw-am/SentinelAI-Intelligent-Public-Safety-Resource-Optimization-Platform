from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.zone import Zone
from app.schemas.zone import ZoneOut, ZoneUpdate

router = APIRouter(prefix="/zones", tags=["Zones"])


@router.get("/", response_model=list[ZoneOut], summary="List all city zones with current risk scores")
def list_zones(db: Session = Depends(get_db)):
    """Returns every zone ordered by risk_score descending — frontend uses this for the heatmap."""
    return db.query(Zone).order_by(Zone.risk_score.desc()).all()


@router.get("/{zone_id}", response_model=ZoneOut, summary="Get a single zone")
def get_zone(zone_id: str, db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")
    return zone


@router.patch("/{zone_id}", response_model=ZoneOut, summary="Update zone metadata / risk score")
def update_zone(zone_id: str, payload: ZoneUpdate, db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    return zone
