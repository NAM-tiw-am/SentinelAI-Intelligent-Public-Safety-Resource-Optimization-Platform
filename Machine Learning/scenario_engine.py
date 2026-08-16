"""
Scenario engine for emergency resource-allocation demo.

Layers scenario-specific risk spikes on top of the ML risk model, then
re-optimises unit assignments and enriches them with route info.

Imports: risk_model.predict_risk, optimizer.optimize_assignment,
         routing.enrich_reassignments
"""

import math, random, json, copy
from datetime import datetime

from risk_model import predict_risk
from optimizer import optimize_assignment
from routing import enrich_reassignments

# ── constants ────────────────────────────────────────────────────────────────
EARTH_R_KM = 6371.0
ADJACENCY_K = 3              # each zone's nearest-K neighbours


# ── haversine helper ─────────────────────────────────────────────────────────
def _haversine_km(lat1, lng1, lat2, lng2):
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return EARTH_R_KM * 2 * math.asin(math.sqrt(a))


# ── 1. ZONE ADJACENCY MAP ───────────────────────────────────────────────────
def build_adjacency(zones: list[dict], k: int = ADJACENCY_K) -> dict[int, list[int]]:
    """Return {zone_id: [nearest-k neighbour zone_ids]} by haversine."""
    adj: dict[int, list[int]] = {}
    for z in zones:
        dists = [
            (_haversine_km(z["lat"], z["lng"], o["lat"], o["lng"]), o["id"])
            for o in zones if o["id"] != z["id"]
        ]
        dists.sort()
        adj[z["id"]] = [zid for _, zid in dists[:k]]
    return adj


# ── 2. SCENARIO SPIKE FUNCTIONS ─────────────────────────────────────────────
def _cap(v: float) -> float:
    return min(v, 1.0)


def apply_festival(risk: dict[int, float], target: int,
                   adj: dict[int, list[int]]) -> dict[int, float]:
    """Festival: target zone ×3.5, adjacent zones ×1.4."""
    risk[target] = _cap(risk[target] * 3.5)
    for n in adj.get(target, []):
        risk[n] = _cap(risk[n] * 1.4)
    return risk


def apply_rally(risk: dict[int, float], target: int) -> dict[int, float]:
    """Rally: target zone ×3.0, no spillover."""
    risk[target] = _cap(risk[target] * 3.0)
    return risk


def apply_storm(risk: dict[int, float]) -> dict[int, float]:
    """Storm: citywide ×1.6, ignores target zone."""
    return {z: _cap(v * 1.6) for z, v in risk.items()}


def apply_multi_incident(risk: dict[int, float], zone_ids: list[int],
                         adj: dict[int, list[int]]) -> dict[int, float]:
    """Multi-incident: each specified zone ×2.2, no spillover."""
    for z in zone_ids:
        risk[z] = _cap(risk[z] * 2.2)
    return risk


def _pick_non_adjacent(adj: dict[int, list[int]], n: int = 3) -> list[int]:
    """Randomly pick n zones that are NOT neighbours of each other."""
    all_ids = list(adj.keys())
    random.shuffle(all_ids)
    picked: list[int] = []
    for z in all_ids:
        # reject if z is adjacent to any already-picked zone
        if any(z in adj.get(p, []) for p in picked):
            continue
        picked.append(z)
        if len(picked) >= n:
            break
    return picked


# ── 3. MAIN ORCHESTRATOR ────────────────────────────────────────────────────
def run_scenario(scenario: str, zone_id: int | None,
                 zones: list[dict], units: list[dict],
                 multi_zone_ids: list[int] | None = None) -> dict:
    """
    1. Compute baseline risk for every zone via predict_risk()
    2. Apply scenario-specific spike
    3. Re-optimise assignments
    4. Enrich with route info
    5. Return {"updated_risk": [...], "reassignments": [...]}
    """
    now = datetime.now()
    is_storm = scenario == "storm"
    weather = "storm" if is_storm else "clear"

    # ── baseline risk scores ─────────────────────────────────────────────
    risk: dict[int, float] = {}
    for z in zones:
        risk[z["id"]] = predict_risk(
            zone_id=z["id"], timestamp=now,
            weather_condition=weather,
            is_event_day=(scenario in ("festival", "rally")),
            expected_crowd_size=5000 if scenario in ("festival", "rally") else 0,
        )

    # ── adjacency (compute once — cheap for 6-10 zones) ─────────────────
    adj = build_adjacency(zones)

    # ── apply scenario spike ─────────────────────────────────────────────
    if scenario == "festival":
        if zone_id is None:
            raise ValueError("festival scenario requires a target zone_id")
        risk = apply_festival(risk, zone_id, adj)

    elif scenario == "rally":
        if zone_id is None:
            raise ValueError("rally scenario requires a target zone_id")
        risk = apply_rally(risk, zone_id)

    elif scenario == "storm":
        risk = apply_storm(risk)

    elif scenario == "multi_incident":
        if multi_zone_ids:
            targets = multi_zone_ids
        else:
            targets = _pick_non_adjacent(adj, n=min(3, len(zones)))
        risk = apply_multi_incident(risk, targets, adj)

    else:
        raise ValueError(f"Unrecognised scenario: '{scenario}'. "
                         f"Choose from: festival, rally, storm, multi_incident")

    # ── update zone dicts with spiked risk scores ────────────────────────
    updated_zones = copy.deepcopy(zones)
    for z in updated_zones:
        z["risk_score"] = round(risk[z["id"]], 4)

    # ── optimise & enrich ────────────────────────────────────────────────
    reassignments = optimize_assignment(units, updated_zones)
    enriched = enrich_reassignments(reassignments, units, updated_zones,
                                    weather_condition=weather, use_osrm=False)

    return {
        "updated_risk": [{"zone_id": z["id"], "risk_score": z["risk_score"]}
                         for z in updated_zones],
        "reassignments": enriched,
    }


# ── demo ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    random.seed(42)

    demo_zones = [
        {"id": 0, "lat": 34.060, "lng": -118.250},
        {"id": 1, "lat": 34.070, "lng": -118.220},
        {"id": 2, "lat": 34.050, "lng": -118.280},
        {"id": 3, "lat": 34.080, "lng": -118.260},
        {"id": 4, "lat": 34.045, "lng": -118.240},
        {"id": 5, "lat": 34.075, "lng": -118.275},
    ]
    demo_units = [
        {"id": "P1", "type": "police",    "lat": 34.050, "lng": -118.280, "status": "available"},
        {"id": "P2", "type": "police",    "lat": 34.051, "lng": -118.279, "status": "available"},
        {"id": "P3", "type": "police",    "lat": 34.075, "lng": -118.275, "status": "available"},
        {"id": "A1", "type": "ambulance", "lat": 34.048, "lng": -118.242, "status": "available"},
        {"id": "A2", "type": "ambulance", "lat": 34.070, "lng": -118.222, "status": "available"},
    ]

    scenarios = [
        ("festival",       0,    None),
        ("rally",          3,    None),
        ("storm",          None, None),
        ("multi_incident", None, [0, 3]),
    ]

    for name, zid, mzids in scenarios:
        print(f"\n{'='*60}")
        print(f"  SCENARIO: {name}"
              + (f"  zone_id={zid}" if zid is not None else "")
              + (f"  multi_zones={mzids}" if mzids else ""))
        print(f"{'='*60}")

        result = run_scenario(name, zid, demo_zones, demo_units,
                              multi_zone_ids=mzids)

        print("  Risk scores:")
        for r in result["updated_risk"]:
            bar = "#" * int(r["risk_score"] * 30)
            print(f"    zone {r['zone_id']}  {r['risk_score']:.4f}  {bar}")

        if result["reassignments"]:
            print("  Reassignments:")
            for m in result["reassignments"]:
                print(f"    {m['unit_id']:3s}  zone {m['from_zone']} -> "
                      f"zone {m['to_zone']}  ETA {m['eta_minutes']:.1f} min")
        else:
            print("  (no reassignments needed)")
