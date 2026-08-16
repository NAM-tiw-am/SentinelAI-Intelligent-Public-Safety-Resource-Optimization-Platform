from sqlalchemy import Column, String, Float, Enum, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
import enum
import uuid
from app.database import Base


class ScenarioType(str, enum.Enum):
    festival = "festival"
    rally = "rally"
    storm = "storm"
    multi_incident = "multi_incident"


class Scenario(Base):
    """
    Tracks scenario simulations triggered by the frontend.
    Each simulation run creates one row so we can replay / audit.
    affected_zones: list of zone_ids hit by the scenario.
    result_snapshot: serialised optimizer output (assignments + routes).
    """
    __tablename__ = "scenarios"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Enum(ScenarioType), nullable=False)
    zone_id = Column(String(10), ForeignKey("zones.id"), nullable=True)  # epicentre
    risk_multiplier = Column(Float, nullable=False, default=1.5)
    affected_zones = Column(JSON, nullable=True, default=list)   # ["Z1", "Z2"]
    result_snapshot = Column(JSON, nullable=True)                # optimizer output

    created_at = Column(DateTime(timezone=True), server_default=func.now())
