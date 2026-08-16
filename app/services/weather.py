"""
weather.py — Live Weather Signal via OpenWeather free tier
===========================================================
Falls back to a mock signal if no API key is configured.
Called by /predict to enrich the ML feature set.
"""

from __future__ import annotations
import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Bhopal city centre (default — change to your target city)
DEFAULT_LAT = 23.2599
DEFAULT_LNG = 77.4126
DEFAULT_CITY = "Bhopal"


def _mock_signal() -> dict:
    """Deterministic fallback when API key is absent."""
    return {
        "condition": "clear",
        "temp_c": 28.0,
        "humidity_pct": 55,
        "wind_kmh": 12,
        "source": "mock",
    }


async def get_weather_signal(lat: float = DEFAULT_LAT, lng: float = DEFAULT_LNG) -> dict:
    """
    Fetch current weather from OpenWeather One-Call API (free tier).
    Returns a normalised dict consumed by the ML risk model.
    """
    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        logger.warning("OPENWEATHER_API_KEY not set — using mock weather signal.")
        return _mock_signal()

    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lng}&appid={api_key}&units=metric"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        return {
            "condition": data["weather"][0]["description"],
            "temp_c": data["main"]["temp"],
            "humidity_pct": data["main"]["humidity"],
            "wind_kmh": round(data["wind"]["speed"] * 3.6, 1),
            "source": "openweather",
        }
    except Exception as exc:
        logger.error(f"Weather API error: {exc} — falling back to mock.")
        return _mock_signal()
