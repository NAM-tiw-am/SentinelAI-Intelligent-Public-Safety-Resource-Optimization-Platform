"""
Human-readable risk explanations for the demo side panel.

Analyses which factors (weather, event, baseline) are driving an elevated
risk score and returns a natural-language sentence picking the top 1-2
contributors.  Phrasing is varied across 4 templates to avoid robotic
repetition when multiple zones are shown together.

No external deps beyond the standard library.
"""

import random

# ── thresholds ───────────────────────────────────────────────────────────────
HIGH_BASELINE_THRESHOLD = 0.12   # zone_base_rate above this = "typically busy"
LARGE_CROWD             = 1000   # crowd size considered significant
ELEVATED_RISK           = 0.35   # below this we say "nothing unusual"

# ── sentence templates (index chosen by zone_id hash for consistency) ────────
_TEMPLATES_TWO = [
    "Risk is elevated primarily due to {a}, compounded by {b}.",
    "High risk driven by {a} alongside {b}.",
    "{a} is the main factor pushing risk up, with {b} adding further pressure.",
    "Elevated risk reflects {a} combined with {b}.",
]
_TEMPLATES_ONE = [
    "Risk is elevated mainly because of {a}.",
    "The primary driver of elevated risk here is {a}.",
    "{a} is pushing this zone's risk above normal levels.",
    "Elevated risk is largely attributable to {a}.",
]
_TEMPLATES_NONE = [
    "Risk level reflects normal patterns for this zone and time.",
    "No unusual factors detected — risk is within typical range.",
    "Current risk aligns with expected baseline conditions.",
    "Nothing out of the ordinary — risk is at routine levels.",
]


def _pick(templates: list[str], zone_id) -> str:
    """Deterministically pick a template variant based on zone_id."""
    return templates[hash(zone_id) % len(templates)]


# ── core explanation function ────────────────────────────────────────────────
def explain_risk(zone_id, risk_score: float, weather_condition: str,
                 is_event_day: bool, expected_crowd_size: int,
                 zone_base_rate: float) -> str:
    """Return a single natural-language sentence explaining the risk score."""

    # Build (factor_description, plausible_weight) pairs
    factors: list[tuple[str, float]] = []

    # Weather factor
    if weather_condition == "storm":
        factors.append(("storm conditions across the city", 0.7))
    elif weather_condition == "rain":
        factors.append(("rainy weather increasing accident likelihood", 0.4))

    # Event factor
    if is_event_day and expected_crowd_size >= LARGE_CROWD:
        factors.append((
            f"an active event (crowd size {expected_crowd_size:,})", 0.9))
    elif is_event_day:
        factors.append(("a nearby scheduled event", 0.5))

    # High baseline factor
    if zone_base_rate >= HIGH_BASELINE_THRESHOLD:
        factors.append((
            f"zone {zone_id}'s typically high incident baseline", 0.3))

    # Sort by plausible weight descending, keep top 2
    factors.sort(key=lambda x: x[1], reverse=True)

    if not factors or risk_score < ELEVATED_RISK:
        return _pick(_TEMPLATES_NONE, zone_id)
    if len(factors) == 1:
        return _pick(_TEMPLATES_ONE, zone_id).format(a=factors[0][0])
    return _pick(_TEMPLATES_TWO, zone_id).format(
        a=factors[0][0], b=factors[1][0])


# ── batch wrapper ────────────────────────────────────────────────────────────
def attach_explanations(updated_risk: list[dict], weather_condition: str,
                        zone_metadata: dict) -> list[dict]:
    """
    Enrich each entry in updated_risk with an 'explanation' string.

    zone_metadata: {zone_id: {"zone_base_rate": float, "is_event_day": bool,
                               "expected_crowd_size": int}}
    """
    enriched = []
    for entry in updated_risk:
        zid = entry["zone_id"]
        meta = zone_metadata.get(zid, {})
        expl = explain_risk(
            zone_id=zid,
            risk_score=entry["risk_score"],
            weather_condition=weather_condition,
            is_event_day=meta.get("is_event_day", False),
            expected_crowd_size=meta.get("expected_crowd_size", 0),
            zone_base_rate=meta.get("zone_base_rate", 0.0),
        )
        enriched.append({**entry, "explanation": expl})
    return enriched


# ── demo ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cases = [
        ("Event + rain",    dict(zone_id=0, risk_score=0.91, weather_condition="rain",
             is_event_day=True,  expected_crowd_size=5000, zone_base_rate=0.15)),
        ("Storm only",      dict(zone_id=3, risk_score=0.72, weather_condition="storm",
             is_event_day=False, expected_crowd_size=0,    zone_base_rate=0.10)),
        ("High baseline",   dict(zone_id=6, risk_score=0.48, weather_condition="clear",
             is_event_day=False, expected_crowd_size=0,    zone_base_rate=0.18)),
        ("Nothing unusual", dict(zone_id=4, risk_score=0.18, weather_condition="clear",
             is_event_day=False, expected_crowd_size=0,    zone_base_rate=0.06)),
    ]

    print("=" * 62)
    print("  Risk Explanation Examples")
    print("=" * 62)
    for label, kwargs in cases:
        expl = explain_risk(**kwargs)
        print(f"\n  [{label}]  risk={kwargs['risk_score']:.2f}")
        print(f"  -> {expl}")
