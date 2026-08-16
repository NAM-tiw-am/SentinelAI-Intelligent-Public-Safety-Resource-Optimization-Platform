from sqlalchemy import Column, String, Float, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class UnitType(str, enum.Enum):
    police = "police"
    ambulance = "ambulance"
    fire = "fire"          # extensible — same code path, different icon


class UnitStatus(str, enum.Enum):
    available = "available"
    busy = "busy"
    en_route = "en_route"
    offline = "offline"


class Unit(Base):
    """
    Represents a single deployable resource (police car, ambulance, etc.).
    lat/lng is the unit's CURRENT position (updated live by optimizer).
    assigned_zone is nullable — None means unassigned / returning to base.
    """
    __tablename__ = "units"

    id = Column(String(10), primary_key=True)             # e.g. "U12"
    type = Column(Enum(UnitType), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    status = Column(Enum(UnitStatus), nullable=False, default=UnitStatus.available)
    assigned_zone = Column(String(10), ForeignKey("zones.id"), nullable=True)
    call_sign = Column(String(50), nullable=True)          # human-readable label

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    assigned_zone_rel = relationship(
        "Zone", back_populates="units", foreign_keys=[assigned_zone]
    )
