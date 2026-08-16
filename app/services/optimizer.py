"""
optimizer.py — Unit Allocation Optimizer
=========================================
STUB: Uses a greedy nearest-unit assignment until Naman wires in OR-Tools.

CONTRACT (don't change signatures — Moksh ↔ Naman interface):
    run_optimizer(zones_with_risk, units)
        → list of Reassignment dicts

Naman: replace `_greedy_assign` body with OR-Tools assignment solver.
The /optimize and /simulate routers just call run_optimizer() — nothing else changes.
"""

from __future__ import annotations
import math
from typing import Any


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance in km (used for ETA estimate in stub)."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _eta_minutes(dist_km: float, speed_kmh: float = 40.0) -> float:
    return round((dist_km / speed_kmh) * 60, 1)


def _greedy_assign(
    zones_with_risk: list[dict],   # [{"id", "centroid_lat", "centroid_lng", "risk_score"}, ...]
    units: list[dict],             # [{"id", "type", "lat", "lng", "status", "assigned_zone"}, ...]
    risk_threshold: float = 0.6,
) -> list[dict[str, Any]]:
    """
    Greedy stub: for each high-risk zone (risk > threshold), find the nearest
    available unit and assign it.

    Naman: replace this with OR-Tools linear assignment / VRP solver.
    Input/output contract must stay identical.
    """
    high_risk = [z for z in zones_with_risk if z["risk_score"] >= risk_threshold]
    high_risk.sort(key=lambda z: z["risk_score"], reverse=True)

    available_units = [u for u in units if u["status"] == "available"]
    reassignments = []
    assigned_unit_ids: set[str] = set()

    for zone in high_risk:
        # Find nearest unassigned available unit
        best_unit = None
        best_dist = float("inf")

        for unit in available_units:
            if unit["id"] in assigned_unit_ids:
                continue
            if unit.get("assigned_zone") == zone["id"]:
                continue   # already there

            dist = _haversine_km(
                unit["lat"], unit["lng"],
                zone["centroid_lat"], zone["centroid_lng"],
            )
            if dist < best_dist:
                best_dist = dist
                best_unit = unit

        if best_unit is None:
            continue

        assigned_unit_ids.add(best_unit["id"])
        reassignments.append({
            "unit_id": best_unit["id"],
            "from_zone": best_unit.get("assigned_zone"),
            "to_zone": zone["id"],
            "eta_minutes": _eta_minutes(best_dist),
            "route": [
                [best_unit["lat"], best_unit["lng"]],
                [zone["centroid_lat"], zone["centroid_lng"]],
            ],
        })

    return reassignments


def run_optimizer(
    zones_with_risk: list[dict],
    units: list[dict],
    risk_threshold: float = 0.6,
) -> list[dict[str, Any]]:
    """
    Public entry point called by /optimize and /simulate routers.
    Returns a list of reassignment dicts matching the SimulateResponse schema.
    """
    return _greedy_assign(zones_with_risk, units, risk_threshold)
