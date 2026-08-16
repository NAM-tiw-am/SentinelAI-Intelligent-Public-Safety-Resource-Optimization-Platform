"""
optimizer.py — Unit Allocation
================================
Tries Naman's OR-Tools CP-SAT optimizer first.
Falls back to a greedy haversine solver if OR-Tools DLLs fail to load
(common with some Anaconda setups on Windows).

The fallback is still "AI-powered decision support" — it's an honest
greedy nearest-unit assignment, clearly labelled in logs.
"""

from __future__ import annotations
import math
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Zone ID maps ───────────────────────────────────────────────────
STR_TO_INT: dict[str, int] = {
    "Z1": 0, "Z2": 1, "Z3": 2,  "Z4": 3,  "Z5": 4,
    "Z6": 5, "Z7": 6, "Z8": 7,  "Z9": 8,  "Z10": 9,
}
INT_TO_STR: dict[int, str] = {v: k for k, v in STR_TO_INT.items()}

# ── Try to import Naman's optimizer ───────────────────────────────
_NAMAN_OK = False
try:
    import app.ml  # adds ML dir to sys.path
    from optimizer import optimize_assignment as _naman_optimize
    from routing import enrich_reassignments as _enrich
    _NAMAN_OK = True
    logger.info("OR-Tools CP-SAT optimizer loaded (Naman's module)")
except Exception as e:
    logger.warning(f"OR-Tools unavailable ({e}) — using greedy fallback")


# ── Greedy fallback ────────────────────────────────────────────────
def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _greedy_fallback(zones_with_risk, units, risk_threshold=0.6):
    high_risk = [z for z in zones_with_risk if z["risk_score"] >= risk_threshold]
    high_risk.sort(key=lambda z: z["risk_score"], reverse=True)
    available = [u for u in units if u["status"] == "available"]
    used: set[str] = set()
    results = []
    for zone in high_risk:
        best, best_dist = None, float("inf")
        for u in available:
            if u["id"] in used:
                continue
            d = _haversine_km(u["lat"], u["lng"], zone["centroid_lat"], zone["centroid_lng"])
            if d < best_dist:
                best_dist, best = d, u
        if best is None:
            continue
        used.add(best["id"])
        eta = round((best_dist / 40.0) * 60, 1)
        results.append({
            "unit_id":     best["id"],
            "from_zone":   best.get("assigned_zone"),
            "to_zone":     zone["id"],
            "eta_minutes": eta,
            "route":       [[best["lat"], best["lng"]],
                            [zone["centroid_lat"], zone["centroid_lng"]]],
        })
    return results


# ── Naman's OR-Tools path ──────────────────────────────────────────
def _map_status(s) -> str:
    s = s if isinstance(s, str) else s.value
    return "assigned" if s in ("busy", "en_route") else "available"


def _run_naman(zones_with_risk, units):
    naman_zones = [
        {"id": STR_TO_INT.get(z["id"], 0), "lat": z["centroid_lat"],
         "lng": z["centroid_lng"], "risk_score": z["risk_score"]}
        for z in zones_with_risk
    ]
    naman_units = [
        {"id": u["id"], "type": u["type"] if isinstance(u["type"], str) else u["type"].value,
         "lat": u["lat"], "lng": u["lng"], "status": _map_status(u["status"])}
        for u in units
    ]
    raw = _naman_optimize(naman_units, naman_zones)
    enriched = _enrich(raw, naman_units, naman_zones)
    results = []
    for r in enriched:
        results.append({
            "unit_id":     r["unit_id"],
            "from_zone":   INT_TO_STR.get(r.get("from_zone")),
            "to_zone":     INT_TO_STR.get(r["to_zone"], "Z1"),
            "eta_minutes": round(float(r.get("eta_minutes", 0.0)), 1),
            "route":       r.get("path", []),
        })
    return results


# ── Public API (called by /optimize and /simulate routers) ─────────
def run_optimizer(
    zones_with_risk: list[dict],
    units: list[dict],
    risk_threshold: float = 0.6,
) -> list[dict[str, Any]]:
    if _NAMAN_OK:
        try:
            return _run_naman(zones_with_risk, units)
        except Exception as e:
            logger.error(f"OR-Tools solver error ({e}) — falling back to greedy")
    return _greedy_fallback(zones_with_risk, units, risk_threshold)
