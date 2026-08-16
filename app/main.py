from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

import app.ml  # ← adds Naman's ML dir to sys.path (must be before ML imports)

from app.config import get_settings
from app.database import engine, Base
from app.models import Zone, Unit, Incident, Scenario   # noqa: ensure models registered
from app.routers import (
    zones_router, units_router, incidents_router,
    predict_router, optimize_router, simulate_router,
)
try:
    from router import router as ml_router  # Naman's ML router
    _ML_ROUTER_OK = True
except Exception as _ml_err:
    ml_router = None
    _ML_ROUTER_OK = False
    import logging as _log
    _log.getLogger(__name__).warning(f"ML router unavailable (OR-Tools DLL): {_ml_err}")
from app.websocket.manager import ws_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


# ── Lifespan: create tables on startup ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating DB tables if not exist …")
    Base.metadata.create_all(bind=engine)
    logger.info("DB ready ✓")
    yield
    logger.info("Shutting down …")


# ── App ───────────────────────────────────────────────────────────
app = FastAPI(
    title="SentinelAI — Emergency Resource Optimizer",
    description=(
        "Backend API for the SentinelAI hackathon project. "
        "Provides zone risk prediction, unit allocation optimization, "
        "scenario simulation, and live WebSocket updates."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (allow Raunak's Vite dev server + Vercel deploy) ─────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST Routers ──────────────────────────────────────────────────
app.include_router(zones_router)
app.include_router(units_router)
app.include_router(incidents_router)
app.include_router(predict_router)
app.include_router(optimize_router)
app.include_router(simulate_router)

# ── Naman's ML Router (/ml/zones/{id}/risk, /ml/optimize, /ml/simulate) ──────
if _ML_ROUTER_OK and ml_router:
    app.include_router(ml_router, prefix="/ml", tags=["ML Engine (Naman)"])


# ── WebSocket endpoint ────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Persistent WebSocket channel for live map updates.
    Frontend connects once and receives:
      - risk_updated   → refresh heatmap
      - unit_reassigned → animate unit markers
      - incident_created → add to incident feed
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client can send "ping"
            data = await websocket.receive_text()
            if data == "ping":
                await ws_manager.send_personal(websocket, "ping", {"status": "ok"})
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)


# ── Health check ──────────────────────────────────────────────────
@app.get("/health", tags=["Meta"])
def health():
    return {"status": "ok", "service": "SentinelAI Backend"}


@app.get("/", tags=["Meta"])
def root():
    return {
        "message": "SentinelAI API — visit /docs for interactive API reference",
        "docs": "/docs",
        "websocket": "ws://localhost:8000/ws",
    }
