"""
ml_service.py — Demand / Risk Prediction
=========================================
Calls Naman's trained XGBoost model (risk_model.py) via the app.ml path bridge.

Zone ID mapping (our string IDs ↔ Naman's integer IDs):
    Z1 → 0  (Downtown Core)
    Z2 → 1  (Riverside East)
    Z3 → 2  (Westfield Park)
    Z4 → 3  (Old Town South)
    Z5 → 4  (Northgate)
    Z6 → 5  (Lakeshore)
    Z7 → 6  (Industrial Yard)
    Z8 → 7  (University Hill)
    Z9 → 8  (Market Quarter)
    Z10 → 9 (Sunset Strip)

CONTRACT (unchanged — routers call this, not Naman's functions directly):
    predict_risk(zones, weather_signal, event_flags, hour_of_day)
        → list of {"zone_id": str, "risk_score": float}
"""

from __future__ import annotations
import app.ml  # ← adds Naman's ML dir to sys.path (must be first)

from datetime import datetime
from typing import Any

# Import Naman's functions
from risk_model import predict_risk as _ml_predict, predict_risk_fallback as _ml_fallback

# ── Zone ID mapping ────────────────────────────────────────────────
STR_TO_INT: dict[str, int] = {
    "Z1": 0, "Z2": 1, "Z3": 2,  "Z4": 3,  "Z5": 4,
    "Z6": 5, "Z7": 6, "Z8": 7,  "Z9": 8,  "Z10": 9,
}


def _normalise_weather(condition: str) -> str:
    """Map OpenWeather descriptions → Naman's 3-class weather encoding."""
    c = condition.lower()
    if any(w in c for w in ("storm", "thunder", "hurricane")):
        return "storm"
    if any(w in c for w in ("rain", "drizzle", "shower", "mist", "fog")):
        return "rain"
    return "clear"


def predict_risk(
    zones: list[dict],
    weather_signal: dict,
    event_flags: dict[str, float],
    hour_of_day: int | None = None,
) -> list[dict[str, Any]]:
    """
    Returns risk scores for each zone using Naman's XGBoost model.
    Falls back to his rule-based scorer if the model throws.
    """
    hour = hour_of_day if hour_of_day is not None else datetime.now().hour
    weather_condition = _normalise_weather(weather_signal.get("condition", "clear"))

    # Build a timestamp object for the model (date doesn't matter — only hour/weekday used)
    ts = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)

    results = []
    for zone in zones:
        zid = zone["id"]
        int_id = STR_TO_INT.get(zid, 0)

        crowd_norm = event_flags.get(zid, 0.0)       # 0-1
        is_event = crowd_norm > 0.0
        crowd_size = int(crowd_norm * 15_000)          # denormalise for model

        try:
            score = _ml_predict(int_id, ts, weather_condition, is_event, crowd_size)
        except Exception:
            # Model load failed → transparent fallback (still "AI-powered decision support")
            score = _ml_fallback(int_id, weather_condition, is_event, crowd_size)

        results.append({"zone_id": zid, "risk_score": round(float(score), 4)})

    return results


def load_historical_density(density_map: dict[str, float]):
    """No-op stub — Naman's model loads zone_base_rate.json internally."""
    pass
