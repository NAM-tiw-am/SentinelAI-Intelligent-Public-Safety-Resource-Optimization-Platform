from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.zone import Zone
from app.services.ml_service import predict_risk
from app.services.weather import get_weather_signal
from datetime import datetime

router = APIRouter(prefix="/predict", tags=["ML Prediction"])

# Mock event calendar — replace with DB table or Naman's event JSON file
_EVENT_CALENDAR: dict[str, float] = {
    # zone_id → normalised crowd size 0-1 (1 = massive event)
}


@router.get("/", summary="Get ML risk predictions for all zones")
async def get_predictions(
    hour: int | None = Query(None, description="Override hour of day (0–23) for testing"),
    lat: float = Query(23.2599, description="City centre lat for weather lookup"),
    lng: float = Query(77.4126, description="City centre lng for weather lookup"),
    db: Session = Depends(get_db),
):
    """
    Runs the ML demand model and returns risk scores per zone.
    Response shape:
        {
          "hour": 14,
          "weather": { "condition": "clear", ... },
          "predictions": [{ "zone_id": "Z1", "risk_score": 0.72 }, ...]
        }
    """
    zones = db.query(Zone).all()
    zone_dicts = [
        {
            "id": z.id,
            "centroid_lat": z.centroid_lat,
            "centroid_lng": z.centroid_lng,
            "risk_score": z.risk_score,
        }
        for z in zones
    ]

    weather = await get_weather_signal(lat, lng)
    effective_hour = hour if hour is not None else datetime.now().hour

    predictions = predict_risk(
        zones=zone_dicts,
        weather_signal=weather,
        event_flags=_EVENT_CALENDAR,
        hour_of_day=effective_hour,
    )

    # Persist updated risk scores back to DB
    pred_map = {p["zone_id"]: p["risk_score"] for p in predictions}
    for zone in zones:
        if zone.id in pred_map:
            zone.risk_score = pred_map[zone.id]
    db.commit()

    return {
        "hour": effective_hour,
        "weather": weather,
        "predictions": predictions,
    }
