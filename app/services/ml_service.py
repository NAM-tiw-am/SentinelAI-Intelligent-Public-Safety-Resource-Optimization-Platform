"""
ml_service.py — Demand / Risk Prediction
=========================================
STUB: Returns defensible rule-based risk scores until Naman wires in the
real XGBoost / gradient-boosting model.

CONTRACT (don't change the function signature — Moksh ↔ Naman interface):
    predict_risk(zones, weather_signal, event_flags, hour_of_day)
        → list of {"zone_id": str, "risk_score": float (0-1)}

Naman: replace the body of `predict_risk` with the real model call.
The router at /predict just calls this function — nothing else changes.
"""

from __future__ import annotations
import math
import random
from datetime import datetime
from typing import Any


# ── Rule-based fallback risk scorer ───────────────────────────────

# Historical incident density per zone — seed from Naman's synthetic data
# Format: {"Z1": 0.6, "Z2": 0.3, ...}
HISTORICAL_DENSITY: dict[str, float] = {}


def _hour_weight(hour: int) -> float:
    """More risk at night (22-03) and evening rush (18-21)."""
    if 22 <= hour or hour <= 3:
        return 1.4
    if 18 <= hour <= 21:
        return 1.2
    if 9 <= hour <= 17:
        return 0.8
    return 1.0


def _weather_weight(weather_signal: dict[str, Any]) -> float:
    """Rain / storm → higher accident/crime risk."""
    condition = weather_signal.get("condition", "clear").lower()
    if "storm" in condition or "thunder" in condition:
        return 1.5
    if "rain" in condition or "drizzle" in condition:
        return 1.2
    return 1.0


def predict_risk(
    zones: list[dict],          # list of zone dicts (id, centroid_lat, centroid_lng, ...)
    weather_signal: dict,       # from weather service
    event_flags: dict[str, float],  # {"Z1": crowd_size_normalized, ...}
    hour_of_day: int | None = None,
) -> list[dict[str, Any]]:
    """
    Returns risk scores for each zone.

    STUB implementation — weighted rule-based scoring:
        score = (historical_density * 0.4)
              + (event_proximity    * 0.3)
              + (weather_penalty    * 0.2)
              + (hour_weight        * 0.1)
    All inputs normalised to [0, 1].

    Naman: swap this body with your trained model inference.
    Keep the return shape identical.
    """
    hour = hour_of_day if hour_of_day is not None else datetime.now().hour
    hw = _hour_weight(hour) / 1.5          # normalise to ~[0,1]
    ww = _weather_weight(weather_signal) / 1.5

    results = []
    for zone in zones:
        zid = zone["id"]
        hist = HISTORICAL_DENSITY.get(zid, random.uniform(0.2, 0.6))
        event = min(event_flags.get(zid, 0.0), 1.0)

        score = (
            hist  * 0.40
            + event * 0.30
            + ww    * 0.20
            + hw    * 0.10
        )
        score = round(min(max(score, 0.0), 1.0), 4)
        results.append({"zone_id": zid, "risk_score": score})

    return results


def load_historical_density(density_map: dict[str, float]):
    """
    Called at startup / after seeding to load Naman's computed
    per-zone historical incident density into memory.
    """
    global HISTORICAL_DENSITY
    HISTORICAL_DENSITY.update(density_map)
