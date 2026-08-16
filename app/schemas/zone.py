from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ZoneOut(BaseModel):
    id: str
    name: str
    centroid_lat: float
    centroid_lng: float
    polygon: list[list[float]]
    risk_score: float = Field(ge=0.0, le=1.0)
    area_sq_km: Optional[float] = None
    population_density: Optional[float] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ZoneUpdate(BaseModel):
    risk_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    area_sq_km: Optional[float] = None
    population_density: Optional[float] = None
