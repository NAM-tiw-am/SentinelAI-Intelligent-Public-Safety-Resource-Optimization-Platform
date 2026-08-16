from sqlalchemy import Column, String, Float, JSON, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Zone(Base):
    """
    Represents one city ward / sector (8–12 zones total).
    polygon is a list of [lat, lng] pairs stored as JSON.
    risk_score is updated live by the ML/optimizer service.
    """
    __tablename__ = "zones"

    id = Column(String(10), primary_key=True)          # e.g. "Z1"
    name = Column(String(100), nullable=False)           # e.g. "MG Road"
    centroid_lat = Column(Float, nullable=False)
    centroid_lng = Column(Float, nullable=False)
    polygon = Column(JSON, nullable=False, default=list) # [[lat,lng], ...]
    risk_score = Column(Float, nullable=False, default=0.0)
    area_sq_km = Column(Float, nullable=True)
    population_density = Column(Float, nullable=True)   # persons / sq-km

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    units = relationship("Unit", back_populates="assigned_zone_rel", foreign_keys="Unit.assigned_zone")
    incidents = relationship("Incident", back_populates="zone_rel")
