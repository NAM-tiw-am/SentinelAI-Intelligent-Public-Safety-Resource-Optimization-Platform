from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.unit import Unit
from app.schemas.unit import UnitOut, UnitUpdate

router = APIRouter(prefix="/units", tags=["Units"])


@router.get("/", response_model=list[UnitOut], summary="List all deployable units")
def list_units(
    type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """Optional filter by ?type=ambulance&status=available"""
    query = db.query(Unit)
    if type:
        query = query.filter(Unit.type == type)
    if status:
        query = query.filter(Unit.status == status)
    return query.all()


@router.get("/{unit_id}", response_model=UnitOut, summary="Get a single unit")
def get_unit(unit_id: str, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail=f"Unit '{unit_id}' not found")
    return unit


@router.patch("/{unit_id}", response_model=UnitOut, summary="Update unit position / status")
def update_unit(unit_id: str, payload: UnitUpdate, db: Session = Depends(get_db)):
    """Called by optimizer after each assignment to persist new lat/lng and status."""
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail=f"Unit '{unit_id}' not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)
    db.commit()
    db.refresh(unit)
    return unit
