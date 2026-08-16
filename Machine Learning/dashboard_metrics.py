"""
Dashboard comparison metrics: optimized vs round-robin baseline assignment.

Computes coverage %, average response times, improvement %, and estimated
overtime savings so the numbers can go straight onto a pitch slide.

Deps: optimizer.optimize_assignment (for the real optimized result)
"""

import math
from optimizer import optimize_assignment

# ── constants ────────────────────────────────────────────────────────────────
EARTH_R_KM    = 6371.0
AVG_SPEED_KMH = 30.0
RISK_THRESHOLD = 0.6          # zones at or above this are "high risk"


def _haversine_km(lat1, lng1, lat2, lng2):
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return EARTH_R_KM * 2 * math.asin(math.sqrt(a))


def _eta_minutes(unit, zone):
    return (_haversine_km(unit["lat"], unit["lng"],
                          zone["lat"], zone["lng"]) / AVG_SPEED_KMH) * 60


# ── baseline: round-robin assignment (ignores risk) ─────────────────────────
def _build_baseline(units: list[dict], zones: list[dict]) -> dict[int, list[dict]]:
    """
    Assign units round-robin to zones sorted by id, separately per unit type.
    Returns {zone_id: [unit, ...]} mapping.
    """
    assignment: dict[int, list[dict]] = {z["id"]: [] for z in zones}
    sorted_zones = sorted(zones, key=lambda z: z["id"])

    for utype in ("police", "ambulance"):
        pool = sorted(
            [u for u in units if u["type"] == utype and u.get("status", "available") == "available"],
            key=lambda u: u["id"],
        )
        for i, unit in enumerate(pool):
            target = sorted_zones[i % len(sorted_zones)]
            assignment[target["id"]].append(unit)

    return assignment


# ── optimized assignment -> same {zone_id: [unit]} structure ────────────────
def _build_optimized(units: list[dict], zones: list[dict]) -> dict[int, list[dict]]:
    """
    Run the CP-SAT optimizer, then map each unit to its assigned zone.
    Units that don't move stay at their nearest zone.
    """
    reassignments = optimize_assignment(units, zones)
    moved = {r["unit_id"]: r["to_zone"] for r in reassignments}

    # Find each unit's current nearest zone
    def nearest_zone(u):
        return min(zones, key=lambda z: _haversine_km(
            u["lat"], u["lng"], z["lat"], z["lng"]))["id"]

    assignment: dict[int, list[dict]] = {z["id"]: [] for z in zones}
    available = [u for u in units if u.get("status", "available") == "available"]
    for u in available:
        dest = moved.get(u["id"], nearest_zone(u))
        assignment[dest].append(u)

    return assignment


# ── metric helpers ───────────────────────────────────────────────────────────
def _coverage_and_response(assignment, zones):
    """Return (coverage_pct, avg_response_min, total_distance_km) for high-risk zones."""
    zone_map = {z["id"]: z for z in zones}
    high_risk = [z for z in zones if z.get("risk_score", 0) >= RISK_THRESHOLD]
    if not high_risk:
        return 100.0, 0.0, 0.0

    covered, etas, total_dist = 0, [], 0.0
    for z in high_risk:
        assigned = assignment.get(z["id"], [])
        if assigned:
            covered += 1
            for u in assigned:
                d = _haversine_km(u["lat"], u["lng"], z["lat"], z["lng"])
                etas.append((d / AVG_SPEED_KMH) * 60)
                total_dist += d

    # Total distance includes ALL assigned units (not just high-risk)
    for zid, unit_list in assignment.items():
        z = zone_map[zid]
        if z.get("risk_score", 0) < RISK_THRESHOLD:
            for u in unit_list:
                total_dist += _haversine_km(u["lat"], u["lng"], z["lat"], z["lng"])

    cov = (covered / len(high_risk)) * 100
    avg_eta = sum(etas) / len(etas) if etas else 0.0
    return cov, avg_eta, total_dist


# ── public API ───────────────────────────────────────────────────────────────
def compute_dashboard_metrics(zones: list[dict], units: list[dict]) -> dict:
    baseline_assign  = _build_baseline(units, zones)
    optimized_assign = _build_optimized(units, zones)

    cov_opt, eta_opt, dist_opt = _coverage_and_response(optimized_assign, zones)
    cov_bas, eta_bas, dist_bas = _coverage_and_response(baseline_assign, zones)

    improvement = ((eta_bas - eta_opt) / eta_bas * 100) if eta_bas > 0 else 0.0
    hours_saved = max(0.0, (dist_bas - dist_opt) / AVG_SPEED_KMH)

    return {
        "coverage_pct":                       round(cov_opt, 1),
        "avg_response_time_minutes":          round(eta_opt, 2),
        "baseline_avg_response_time_minutes": round(eta_bas, 2),
        "response_time_improvement_pct":      round(improvement, 1),
        "overtime_hours_saved_estimate":       round(hours_saved, 2),
    }


# ── demo ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    demo_zones = [
        {"id": 0, "lat": 34.060, "lng": -118.250, "risk_score": 0.92},
        {"id": 1, "lat": 34.070, "lng": -118.220, "risk_score": 0.65},
        {"id": 2, "lat": 34.050, "lng": -118.280, "risk_score": 0.30},
        {"id": 3, "lat": 34.080, "lng": -118.260, "risk_score": 0.88},
        {"id": 4, "lat": 34.045, "lng": -118.240, "risk_score": 0.40},
        {"id": 5, "lat": 34.075, "lng": -118.275, "risk_score": 0.78},
    ]
    demo_units = [
        {"id": "P1", "type": "police",    "lat": 34.050, "lng": -118.280, "status": "available"},
        {"id": "P2", "type": "police",    "lat": 34.048, "lng": -118.278, "status": "available"},
        {"id": "P3", "type": "police",    "lat": 34.047, "lng": -118.282, "status": "available"},
        {"id": "A1", "type": "ambulance", "lat": 34.049, "lng": -118.281, "status": "available"},
        {"id": "A2", "type": "ambulance", "lat": 34.046, "lng": -118.279, "status": "available"},
    ]

    metrics = compute_dashboard_metrics(demo_zones, demo_units)

    print("=" * 55)
    print("  Dashboard Metrics: Optimized vs Round-Robin Baseline")
    print("=" * 55)
    for k, v in metrics.items():
        label = k.replace("_", " ").title()
        unit = "%" if "pct" in k else ("hrs" if "hours" in k else "min")
        print(f"  {label:45s} {v:>7.2f} {unit}")
