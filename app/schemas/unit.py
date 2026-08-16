from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.unit import UnitType, UnitStatus


class UnitOut(BaseModel):
    id: str
    type: UnitType
    lat: float
    lng: float
    status: UnitStatus
    assigned_zone: Optional[str] = None
    call_sign: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UnitUpdate(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    status: Optional[UnitStatus] = None
    assigned_zone: Optional[str] = None
