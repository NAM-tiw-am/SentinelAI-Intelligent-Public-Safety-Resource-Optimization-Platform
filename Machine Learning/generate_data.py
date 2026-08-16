"""
Synthetic incident data generator for police + ambulance resource allocation demo.
Outputs: zones.json, events.json, incidents.csv
Run:  python generate_data.py
Deps: numpy, pandas (standard Anaconda / pip install)
"""
import json, random, pathlib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ── reproducibility ──────────────────────────────────────────────────────────
SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

OUT = pathlib.Path(__file__).parent

# ── 1. ZONES — fictitious mid-size city "Lakeport" ──────────────────────────
ZONES = [
    {"id": i, "name": n, "lat": lat, "lng": lng}
    for i, (n, lat, lng) in enumerate([
        ("Downtown Core",   34.060, -118.250), ("Riverside East",  34.070, -118.220),
        ("Westfield Park",  34.050, -118.280), ("Old Town South",  34.040, -118.250),
        ("Northgate",       34.080, -118.260), ("Lakeshore",       34.055, -118.230),
        ("Industrial Yard", 34.045, -118.270), ("University Hill", 34.075, -118.240),
        ("Market Quarter",  34.065, -118.265), ("Sunset Strip",    34.085, -118.275),
    ])
]
# Zone-specific base incident rates (avg incidents / day)
ZONE_BASE_RATE = {0: 5.0, 1: 3.0, 2: 2.5, 3: 4.0, 4: 2.0,
                  5: 3.5, 6: 4.5, 7: 2.0, 8: 3.0, 9: 3.5}

# ── 2. EVENTS — 18 events over a 90-day window ──────────────────────────────
START_DATE = datetime(2026, 5, 1)
EVENT_TYPES = ["festival", "rally", "concert", "sports_match"]
events = []
for _ in range(18):
    events.append({
        "zone_id":             int(rng.integers(0, 10)),
        "date":                (START_DATE + timedelta(days=int(rng.integers(0, 90)))).strftime("%Y-%m-%d"),
        "event_type":          random.choice(EVENT_TYPES),
        "expected_crowd_size": int(rng.integers(500, 15001)),
    })
event_lookup = {}  # (date_str, zone_id) -> max crowd_size for that combo
for e in events:
    key = (e["date"], int(e["zone_id"]))
    event_lookup[key] = max(event_lookup.get(key, 0), e["expected_crowd_size"])

# ── 3. INCIDENTS — 3 000 rows with realism rules ────────────────────────────
TYPES = ["theft", "assault", "medical_emergency", "accident", "disturbance", "fire"]
TYPE_WEIGHTS_BASE = np.array([0.28, 0.15, 0.18, 0.18, 0.15, 0.06])  # baseline mix
WEATHER_OPTS = ["clear", "rain", "storm"]
WEATHER_PROBS = [0.60, 0.28, 0.12]

# Severity distributions per type (index 0-4 → severity 1-5)
SEV = {
    "theft":              [0.30, 0.35, 0.20, 0.10, 0.05],
    "assault":            [0.10, 0.20, 0.30, 0.25, 0.15],
    "medical_emergency":  [0.15, 0.25, 0.30, 0.20, 0.10],
    "accident":           [0.05, 0.15, 0.30, 0.30, 0.20],
    "disturbance":        [0.25, 0.35, 0.25, 0.10, 0.05],
    "fire":               [0.05, 0.10, 0.25, 0.35, 0.25],
}

rows = []
total_days = 90
target_rows = 3000
# Pre-compute per-day, per-zone expected counts then Poisson-sample
for day_offset in range(total_days):
    dt = START_DATE + timedelta(days=day_offset)
    date_str = dt.strftime("%Y-%m-%d")
    weekday = dt.weekday()          # 0=Mon … 6=Sun
    is_weekend = weekday >= 5
    weather = rng.choice(WEATHER_OPTS, p=WEATHER_PROBS)

    for zone in ZONES:
        zid = zone["id"]
        rate = ZONE_BASE_RATE[zid]

        # Weekend boost for disturbance/accident (applied later per-type)
        weekend_factor = 1.3 if is_weekend else 1.0
        # Weather multiplier for accident & medical
        wx_factor = {"clear": 1.0, "rain": 1.3, "storm": 2.0}[weather]
        # Event-day multiplier (scaled by crowd size: 2× at 500, 4× at 15 000)
        crowd = event_lookup.get((date_str, zid), 0)
        event_factor = 1.0
        is_event = crowd > 0
        if is_event:
            event_factor = 2.0 + 2.0 * (crowd - 500) / 14500  # linear 2→4

        effective_rate = rate * event_factor
        # Scale so total ≈ 3 000 over 90 days (sum of base rates = 33/day → ~2970)
        n_incidents = rng.poisson(effective_rate)

        for _ in range(n_incidents):
            # Hour of day — uniform baseline, then type chosen conditioned on hour
            hour = int(rng.integers(0, 24))
            weights = TYPE_WEIGHTS_BASE.copy()

            # Assault/disturbance spike 22:00-04:00
            if hour >= 22 or hour < 4:
                weights[1] *= 2.5   # assault
                weights[4] *= 2.5   # disturbance

            # Medical emergency slight afternoon/evening bump
            if 14 <= hour <= 22:
                weights[2] *= 1.4

            # Weekend boost
            if is_weekend:
                weights[4] *= weekend_factor   # disturbance
                weights[3] *= weekend_factor   # accident

            # Weather boost
            if weather != "clear":
                weights[3] *= wx_factor   # accident
                weights[2] *= wx_factor   # medical_emergency

            weights /= weights.sum()
            inc_type = rng.choice(TYPES, p=weights)

            severity = int(rng.choice([1, 2, 3, 4, 5], p=SEV[inc_type]))
            ts = dt + timedelta(hours=int(hour), minutes=int(rng.integers(0, 60)),
                                seconds=int(rng.integers(0, 60)))

            rows.append({
                "incident_id":      len(rows) + 1,
                "timestamp":        ts.isoformat(),
                "zone_id":          zid,
                "type":             inc_type,
                "severity":         severity,
                "weather_condition": weather,
                "is_event_day":     is_event,
            })

# ── 4. WRITE OUTPUT ──────────────────────────────────────────────────────────
(OUT / "zones.json").write_text(json.dumps(ZONES, indent=2))
(OUT / "events.json").write_text(json.dumps(events, indent=2))
df = pd.DataFrame(rows)
df.to_csv(OUT / "incidents.csv", index=False)

# ── 5. SUMMARY ──────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  Generated {len(df)} incidents over {total_days} days")
print(f"{'='*50}")
print(f"\n> By type:\n{df['type'].value_counts().to_string()}")
print(f"\n> By zone:\n{df['zone_id'].value_counts().sort_index().to_string()}")
print(f"\n> By weather:\n{df['weather_condition'].value_counts().to_string()}")
print(f"\n> Event-day incidents: {df['is_event_day'].sum()}  "
      f"({df['is_event_day'].mean()*100:.1f}%)")
print(f"\n> Severity mean: {df['severity'].mean():.2f}  median: {df['severity'].median():.0f}")
