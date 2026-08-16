"""
CP-SAT optimizer for police + ambulance unit-to-zone assignment.

Solves police and ambulance independently. Uses coverage constraints
(risk >= 0.6 -> 1 unit, risk >= 0.85 -> 2 units) and minimizes total
haversine travel distance with heavy penalties for leaving high-risk
zones uncovered.

Inputs : units [{id, type, lat, lng, status}], zones [{id, lat, lng, risk_score}]
Output : list of reassignments [{unit_id, from_zone, to_zone, eta_minutes}]
Deps   : ortools
"""

import math
from ortools.sat.python import cp_model

# ── constants ────────────────────────────────────────────────────────────────
EARTH_R_KM   = 6371.0
AVG_SPEED_KMH = 30.0          # city-traffic placeholder
COST_SCALE    = 10_000         # multiplier to keep ints precise for CP-SAT
UNCOV_PENALTY = 500_000_000    # per-unit-of-slack, scaled by risk²


# ── haversine ────────────────────────────────────────────────────────────────
def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in kilometres."""
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return EARTH_R_KM * 2 * math.asin(math.sqrt(a))


def _nearest_zone_id(unit, zones):
    """Return the zone id closest to a unit's current position."""
    return min(zones, key=lambda z: haversine_km(
        unit["lat"], unit["lng"], z["lat"], z["lng"]))["id"]


# ── solver for one unit type ─────────────────────────────────────────────────
def _solve_type(type_units, zones):
    """Build and solve a CP-SAT model for a single unit type (police OR ambulance)."""
    U = len(type_units)
    Z = len(zones)
    if U == 0:
        return []

    # Pre-compute current zone and integer distance matrix
    cur_zone = [_nearest_zone_id(u, zones) for u in type_units]
    dist_km  = [[haversine_km(type_units[u]["lat"], type_units[u]["lng"],
                               zones[z]["lat"], zones[z]["lng"])
                  for z in range(Z)] for u in range(U)]
    # Scale to integer costs (metres × 10 for sub-metre precision)
    cost = [[int(dist_km[u][z] * COST_SCALE) for z in range(Z)] for u in range(U)]

    # ── coverage requirements per zone ───────────────────────────────────
    required = []
    for z in zones:
        if z["risk_score"] >= 0.85:
            required.append(min(2, U))     # 2 units if enough exist
        elif z["risk_score"] >= 0.60:
            required.append(1)
        else:
            required.append(0)

    # ── CP-SAT model ─────────────────────────────────────────────────────
    mdl = cp_model.CpModel()

    # x[u, z] = 1 iff unit u is assigned to zone z
    x = {(u, z): mdl.new_bool_var(f"x_{u}_{z}")
         for u in range(U) for z in range(Z)}

    # Each unit assigned to exactly one zone
    for u in range(U):
        mdl.add(sum(x[u, z] for z in range(Z)) == 1)

    # Coverage: introduce slack so the model stays feasible when units < need
    slack = {}
    for z in range(Z):
        if required[z] > 0:
            slack[z] = mdl.new_int_var(0, required[z], f"slack_{z}")
            mdl.add(sum(x[u, z] for u in range(U)) + slack[z] >= required[z])

    # ── objective: distance + coverage-gap penalty ───────────────────────
    obj = []
    # (a) total travel distance
    for u in range(U):
        for z in range(Z):
            obj.append(cost[u][z] * x[u, z])       # int * BoolVar -> LinearExpr
    # (b) penalty for each unit of coverage deficit, weighted by risk²
    for z in slack:
        risk_w = int(zones[z]["risk_score"] ** 2 * 100)   # 0-100 int weight
        obj.append(UNCOV_PENALTY * risk_w * slack[z])

    mdl.minimize(sum(obj))

    # ── solve ────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.solve(mdl)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []

    # ── extract only actual moves ────────────────────────────────────────
    moves = []
    for u in range(U):
        for z in range(Z):
            if solver.value(x[u, z]) == 1:
                new_zone = zones[z]["id"]
                if new_zone != cur_zone[u]:
                    d = dist_km[u][z]
                    eta = (d / AVG_SPEED_KMH) * 60       # minutes
                    moves.append({
                        "unit_id":     type_units[u]["id"],
                        "from_zone":   cur_zone[u],
                        "to_zone":     new_zone,
                        "eta_minutes": round(eta, 1),
                    })
    return moves


# ── public API ───────────────────────────────────────────────────────────────
def optimize_assignment(units: list[dict], zones: list[dict]) -> list[dict]:
    """
    Solve unit-to-zone assignment separately for police and ambulance.

    Returns a list of reassignment dicts only for units whose zone changed:
        [{"unit_id", "from_zone", "to_zone", "eta_minutes"}, ...]
    """
    results: list[dict] = []
    for unit_type in ("police", "ambulance"):
        available = [u for u in units if u["type"] == unit_type
                     and u["status"] == "available"]
        if available:
            results.extend(_solve_type(available, zones))
    return results


# ── demo / sanity-check ─────────────────────────────────────────────────────
if __name__ == "__main__":
    # 4 zones with mixed risk scores  (coords near "Lakeport" from zones.json)
    demo_zones = [
        {"id": 0, "lat": 34.060, "lng": -118.250, "risk_score": 0.90},  # high
        {"id": 1, "lat": 34.070, "lng": -118.220, "risk_score": 0.65},  # medium
        {"id": 2, "lat": 34.050, "lng": -118.280, "risk_score": 0.30},  # low
        {"id": 3, "lat": 34.080, "lng": -118.260, "risk_score": 0.88},  # high
    ]
    # 5 units — 3 police, 2 ambulance; positions don't match optimal zones
    demo_units = [
        {"id": "P1", "type": "police",    "lat": 34.050, "lng": -118.280, "status": "available"},
        {"id": "P2", "type": "police",    "lat": 34.051, "lng": -118.279, "status": "available"},
        {"id": "P3", "type": "police",    "lat": 34.048, "lng": -118.282, "status": "available"},
        {"id": "A1", "type": "ambulance", "lat": 34.052, "lng": -118.278, "status": "available"},
        {"id": "A2", "type": "ambulance", "lat": 34.049, "lng": -118.281, "status": "available"},
    ]

    print("Zones:")
    for z in demo_zones:
        print(f"  id={z['id']}  risk={z['risk_score']:.2f}  ({z['lat']}, {z['lng']})")
    print("\nUnits:")
    for u in demo_units:
        nearest = _nearest_zone_id(u, demo_zones)
        print(f"  {u['id']:3s}  {u['type']:10s}  nearest_zone={nearest}  ({u['lat']}, {u['lng']})")

    moves = optimize_assignment(demo_units, demo_zones)

    print(f"\n{'='*60}")
    print(f"  Reassignments: {len(moves)}")
    print(f"{'='*60}")
    if not moves:
        print("  (no units need to move)")
    for m in moves:
        print(f"  {m['unit_id']:3s}  zone {m['from_zone']} -> zone {m['to_zone']}"
              f"   ETA {m['eta_minutes']:.1f} min")
