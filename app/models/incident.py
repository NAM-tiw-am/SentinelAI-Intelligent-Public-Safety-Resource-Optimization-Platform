from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from app.database import Base


class IncidentType(str, enum.Enum):
    crime = "crime"
    medical = "medical"
    accident = "accident"
    fire = "fire"
    crowd_control = "crowd_control"
    other = "other"


class IncidentStatus(str, enum.Enum):
    predicted = "predicted"   # ML flagged — not yet confirmed
    active = "active"         # live / dispatched
    resolved = "resolved"


class Incident(Base):
    """
    One incident record — can be ML-predicted or manually reported.
    severity: 1 (low) → 5 (critical).
    """
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    zone_id = Column(String(10), ForeignKey("zones.id"), nullable=False)
    type = Column(Enum(IncidentType), nullable=False, default=IncidentType.other)
    severity = Column(Integer, nullable=False, default=3)   # 1-5
    status = Column(Enum(IncidentStatus), nullable=False, default=IncidentStatus.predicted)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    zone_rel = relationship("Zone", back_populates="incidents")
