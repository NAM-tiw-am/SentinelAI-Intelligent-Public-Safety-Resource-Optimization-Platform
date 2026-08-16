from app.routers.zones import router as zones_router
from app.routers.units import router as units_router
from app.routers.incidents import router as incidents_router
from app.routers.predict import router as predict_router
from app.routers.optimize import router as optimize_router
from app.routers.simulate import router as simulate_router

__all__ = [
    "zones_router", "units_router", "incidents_router",
    "predict_router", "optimize_router", "simulate_router",
]
