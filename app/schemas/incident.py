from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.incident import IncidentType, IncidentStatus


class IncidentCreate(BaseModel):
    zone_id: str
    type: IncidentType = IncidentType.other
    severity: int = 3          # 1-5
    lat: Optional[float] = None
    lng: Optional[float] = None
    description: Optional[str] = None
    timestamp: Optional[datetime] = None


class IncidentOut(BaseModel):
    id: str
    zone_id: str
    type: IncidentType
    severity: int
    status: IncidentStatus
    lat: Optional[float] = None
    lng: Optional[float] = None
    description: Optional[str] = None
    timestamp: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
