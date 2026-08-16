# SentinelAI — Backend API

FastAPI + PostgreSQL backend for the SentinelAI emergency resource optimizer.

---

## Quick Start

### 1. Fill in your DB credentials
Edit `.env`:
```
DB_USER=your_postgres_username
DB_PASSWORD=your_postgres_password
DB_NAME=your_database_name
```

### 2. Create the PostgreSQL database
```sql
CREATE DATABASE your_database_name;
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the server
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Seed the database
```bash
python -m seed.seed_data
```

### 6. Open Swagger UI
Visit [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/zones` | All zones with current risk scores |
| GET | `/zones/{id}` | Single zone |
| PATCH | `/zones/{id}` | Update zone risk score |
| GET | `/units` | All units (filter: `?type=police&status=available`) |
| GET | `/units/{id}` | Single unit |
| PATCH | `/units/{id}` | Update unit position / status |
| GET | `/incidents` | Incident list (filter: `?status=active&zone_id=Z1`) |
| POST | `/incidents` | Report a new incident |
| PATCH | `/incidents/{id}/status` | Update incident status |
| GET | `/predict` | Run ML risk prediction for all zones |
| POST | `/optimize` | Run optimizer → reassign units |
| **POST** | **`/simulate`** | **Run scenario simulation (demo centrepiece)** |
| WS | `/ws` | Live WebSocket channel |
| GET | `/health` | Health check |

## WebSocket Events

Connect to `ws://localhost:8000/ws`. You'll receive JSON messages:

```json
{ "event": "risk_updated",    "data": { "scenario": "rally", "updated_risk": [...] } }
{ "event": "unit_reassigned", "data": { "reassignments": [...] } }
{ "event": "incident_created","data": { "id": "...", "zone_id": "Z4", ... } }
```

## Simulate Request (demo centrepiece)

```bash
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario": "rally", "zone_id": "Z4"}'
```

Response shape:
```json
{
  "scenario_id": "...",
  "scenario": "rally",
  "updated_risk": [{ "zone_id": "Z4", "risk_score": 0.95 }],
  "reassignments": [{ "unit_id": "P02", "from_zone": "Z2", "to_zone": "Z4", "eta_minutes": 4.2 }],
  "coverage_pct": 70.0,
  "avg_response_time_minutes": 5.1
}
```

---

## Project Structure

```
sentinelai-backend/
├── app/
│   ├── main.py          # FastAPI app entry point
│   ├── config.py        # Settings (reads .env)
│   ├── database.py      # SQLAlchemy engine + session
│   ├── models/          # ORM models (Zone, Unit, Incident, Scenario)
│   ├── schemas/         # Pydantic request/response shapes
│   ├── routers/         # REST route handlers
│   ├── services/
│   │   ├── ml_service.py   # ← Naman wires model here
│   │   ├── optimizer.py    # ← Naman wires OR-Tools here
│   │   └── weather.py      # OpenWeather API
│   └── websocket/
│       └── manager.py   # WS connection manager
└── seed/
    └── seed_data.py     # DB seed script
```

## Integration Points for Naman

1. **`app/services/ml_service.py`** — Replace body of `predict_risk()` with your XGBoost inference. Keep the function signature identical.
2. **`app/services/optimizer.py`** — Replace `_greedy_assign()` body with OR-Tools assignment solver. Keep `run_optimizer()` signature identical.
3. **`seed/seed_data.py`** — Replace `make_incidents()` with your synthetic data generator. Zone IDs must stay Z1–Z10.

## Deployment (Render / Railway)

1. Push to GitHub
2. Create a PostgreSQL service on Render/Railway
3. Add environment variables from `.env` to the service dashboard
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
5. Add Raunak's Vercel URL to `CORS_ORIGINS`
