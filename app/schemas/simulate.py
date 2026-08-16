from pydantic import BaseModel
from typing import Optional
from app.models.scenario import ScenarioType


# ── Request ────────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    """
    POST /simulate body — matches the integration contract in the plan:
        { "scenario": "festival", "zone_id": "Z1" }
    """
    scenario: ScenarioType
    zone_id: Optional[str] = None        # epicentre zone (optional)


# ── Response sub-models ────────────────────────────────────────────

class RiskUpdate(BaseModel):
    zone_id: str
    risk_score: float


class Reassignment(BaseModel):
    unit_id: str
    from_zone: Optional[str]
    to_zone: str
    eta_minutes: float
    route: Optional[list[list[float]]] = None   # [[lat,lng], ...] path points


class SimulateResponse(BaseModel):
    """
    Matches the integration contract response shape from the plan.
    """
    scenario_id: str
    scenario: ScenarioType
    updated_risk: list[RiskUpdate]
    reassignments: list[Reassignment]
    coverage_pct: Optional[float] = None
    avg_response_time_minutes: Optional[float] = None
