"""
Route computation for unit-to-zone reassignments.

Provides haversine-based routing (always available) with optional OSRM
integration for real road-network routes.  The get_route() wrapper handles
fallback automatically.

Deps: requests (only needed if use_osrm=True)
"""

import math
import json

# ── constants ────────────────────────────────────────────────────────────────
EARTH_R_KM = 6371.0

# Base speeds (km/h) by unit type — ambulance gets traffic priority
BASE_SPEED = {"police": 35.0, "ambulance": 42.0}

# Weather multipliers on speed (lower = slower)
WEATHER_SPEED_FACTOR = {"clear": 1.0, "rain": 0.80, "storm": 0.70}

OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"
OSRM_TIMEOUT_S = 5


# ── haversine ────────────────────────────────────────────────────────────────
def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres."""
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return EARTH_R_KM * 2 * math.asin(math.sqrt(a))


# ── 1. core haversine route ─────────────────────────────────────────────────
def compute_route(unit: dict, target_zone: dict,
                  weather_condition: str = "clear") -> dict:
    """
    Compute route using haversine distance + assumed city speed.

    Returns {"eta_minutes": float, "path": [[lat,lng], [lat,lng]]}.
    Path is a straight line (start -> end) — good enough until OSRM is wired.
    """
    dist_km = _haversine_km(unit["lat"], unit["lng"],
                            target_zone["lat"], target_zone["lng"])

    speed = BASE_SPEED.get(unit.get("type", "police"), 35.0)
    speed *= WEATHER_SPEED_FACTOR.get(weather_condition, 1.0)

    eta = (dist_km / speed) * 60.0 if speed > 0 else 0.0  # minutes

    path = [
        [unit["lat"], unit["lng"]],
        [target_zone["lat"], target_zone["lng"]],
    ]
    return {"eta_minutes": round(eta, 1), "path": path}


# ── 2. optional OSRM integration ────────────────────────────────────────────
def compute_route_osrm(unit: dict, target_zone: dict) -> dict | None:
    """
    Call the public OSRM demo server for a real driving route.

    Returns {"eta_minutes": float, "path": [[lat,lng], ...]} on success,
    or None on any failure so the caller can fall back gracefully.

    NOTE: OSRM uses (lng, lat) order in URLs but we store (lat, lng).
    """
    try:
        import requests                     # deferred import — only needed here
        import polyline as polyline_lib     # optional; we decode manually below
    except ImportError:
        pass                                # polyline lib not required

    try:
        import requests
        coords = (f"{unit['lng']},{unit['lat']}"
                  f";{target_zone['lng']},{target_zone['lat']}")
        url = f"{OSRM_BASE_URL}/{coords}"
        resp = requests.get(url, params={"overview": "full", "geometries": "geojson"},
                            timeout=OSRM_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            return None

        route = data["routes"][0]
        duration_min = route["duration"] / 60.0                 # seconds -> min
        # GeoJSON coords are [lng, lat]; flip to [lat, lng] for our convention
        geojson_coords = route["geometry"]["coordinates"]
        path = [[c[1], c[0]] for c in geojson_coords]

        return {"eta_minutes": round(duration_min, 1), "path": path}

    except Exception:
        return None                         # any error -> caller falls back


# ── 3. wrapper with automatic fallback ───────────────────────────────────────
def get_route(unit: dict, target_zone: dict,
              weather_condition: str = "clear",
              use_osrm: bool = False) -> dict:
    """
    Try OSRM if requested; fall back to haversine on failure or if disabled.
    """
    if use_osrm:
        result = compute_route_osrm(unit, target_zone)
        if result is not None:
            return result                    # OSRM succeeded

    return compute_route(unit, target_zone, weather_condition)


# ── 4. enrich a batch of optimizer reassignments ─────────────────────────────
def enrich_reassignments(reassignments: list[dict],
                         units: list[dict],
                         zones: list[dict],
                         weather_condition: str = "clear",
                         use_osrm: bool = False) -> list[dict]:
    """
    For each reassignment dict from the optimizer, look up the unit and
    target zone, compute the route, and merge eta_minutes + path in-place.
    """
    unit_map = {u["id"]: u for u in units}
    zone_map = {z["id"]: z for z in zones}

    enriched = []
    for r in reassignments:
        unit = unit_map.get(r["unit_id"])
        zone = zone_map.get(r["to_zone"])
        if unit is None or zone is None:
            enriched.append(r)              # can't route — pass through unchanged
            continue

        route = get_route(unit, zone, weather_condition, use_osrm)

        enriched.append({
            **r,
            "eta_minutes": route["eta_minutes"],
            "path":        route["path"],
        })
    return enriched


# ── demo ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    demo_units = [
        {"id": "P1", "type": "police",    "lat": 34.050, "lng": -118.280},
        {"id": "P2", "type": "police",    "lat": 34.051, "lng": -118.279},
        {"id": "A1", "type": "ambulance", "lat": 34.052, "lng": -118.278},
    ]
    demo_zones = [
        {"id": 0, "lat": 34.060, "lng": -118.250},
        {"id": 3, "lat": 34.080, "lng": -118.260},
    ]
    # Simulated optimizer output
    demo_reassignments = [
        {"unit_id": "P1", "from_zone": 2, "to_zone": 0, "eta_minutes": 0},
        {"unit_id": "P2", "from_zone": 2, "to_zone": 3, "eta_minutes": 0},
        {"unit_id": "A1", "from_zone": 2, "to_zone": 0, "eta_minutes": 0},
    ]

    result = enrich_reassignments(
        demo_reassignments, demo_units, demo_zones,
        weather_condition="rain", use_osrm=False,
    )

    print("=" * 60)
    print("  Enriched reassignments (haversine, weather=rain)")
    print("=" * 60)
    for r in result:
        print(json.dumps(r, indent=2))
        print()
