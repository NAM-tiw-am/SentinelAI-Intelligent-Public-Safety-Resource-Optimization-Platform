# SentinelAI — Machine Learning Module

> Intelligent Public Safety Resource Optimization Platform

This module contains the complete ML pipeline for **predicting zone-level crime/incident risk** and **optimally assigning police + ambulance units** to city zones using constraint-based optimization.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [File Descriptions](#file-descriptions)
- [Setup & Installation](#setup--installation)
- [How to Run](#how-to-run)
- [API Endpoints](#api-endpoints)
- [Pipeline Flow](#pipeline-flow)
- [Project Structure](#project-structure)

---

## Architecture Overview

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  generate_data   │────▶│   risk_model     │────▶│   optimizer      │
│  (synthetic data)│     │  (XGBoost train  │     │  (CP-SAT solver) │
│                  │     │   + inference)   │     │                  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                │                         │
                                ▼                         ▼
                         ┌──────────────────┐     ┌──────────────────┐
                         │ scenario_engine  │     │    routing       │
                         │ (what-if sims)   │     │ (haversine/OSRM) │
                         └──────────────────┘     └──────────────────┘
                                │                         │
                                ▼                         ▼
                         ┌──────────────────┐     ┌──────────────────┐
                         │   router.py      │     │ dashboard_metrics│
                         │  (FastAPI API)   │     │ (KPI comparison) │
                         └──────────────────┘     └──────────────────┘
                                │
                                ▼
                         ┌──────────────────┐
                         │ explainability   │
                         │ (human-readable  │
                         │  risk reasons)   │
                         └──────────────────┘
```

---

## File Descriptions

| File | Purpose | Lines |
|------|---------|-------|
| `generate_data.py` | Generates synthetic incident data with realistic patterns (time-of-day spikes, weather effects, event-day multipliers). Outputs `zones.json`, `events.json`, `incidents.csv` | ~150 |
| `risk_model.py` | Aggregates incidents into zone-hour buckets, trains an XGBoost regressor on severity-weighted risk scores (0–1), and exposes `predict_risk()` / `predict_risk_fallback()` for inference | ~190 |
| `optimizer.py` | Uses Google OR-Tools CP-SAT solver to assign police and ambulance units to zones, enforcing risk-based coverage constraints while minimizing travel distance | ~145 |
| `routing.py` | Computes routes between units and zones using haversine distance (with optional OSRM integration for real road-network routes). Includes ETA estimation adjusted for unit type and weather | ~140 |
| `scenario_engine.py` | Runs what-if simulations (festival, rally, storm, multi-incident) by applying scenario-specific risk multipliers then re-optimizing assignments | ~170 |
| `router.py` | FastAPI APIRouter exposing `/health`, `/zones/{id}/risk`, `/optimize`, and `/simulate` endpoints with Pydantic request/response models | ~140 |
| `dashboard_metrics.py` | Computes dashboard KPIs comparing optimized assignment vs naive round-robin baseline (coverage %, response time improvement, overtime savings) | ~115 |
| `explainability.py` | Generates human-readable explanations for elevated risk scores, suitable for a live demo side panel | ~95 |

### Generated Data Files

| File | Description |
|------|-------------|
| `zones.json` | 10 city zones with id, name, lat, lng |
| `events.json` | 18 events across 90 days (festival, rally, concert, sports_match) |
| `incidents.csv` | ~3,000 incident rows with timestamp, zone, type, severity, weather, event-day flag |
| `model.json` | Trained XGBoost model (native format) |
| `zone_base_rate.json` | Per-zone historical mean risk scores |

---

## Setup & Installation

### Prerequisites

- **Python 3.10+** (tested on 3.11)
- **pip** (Python package manager)

### Step 1: Clone the Repository

```bash
git clone https://github.com/NAM-tiw-am/SentinelAI-Intelligent-Public-Safety-Resource-Optimization-Platform.git
cd SentinelAI-Intelligent-Public-Safety-Resource-Optimization-Platform/Machine\ Learning
```

### Step 2: Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## How to Run

The scripts should be run **in order** the first time, since each step generates files needed by the next.

### Step 1: Generate Synthetic Data

```bash
python generate_data.py
```

**Output:** Creates `zones.json`, `events.json`, and `incidents.csv` with ~3,000 realistic incident records.

**What to expect:**
```
==================================================
  Generated 3123 incidents over 90 days
==================================================

> By type:
theft                711
accident             627
medical_emergency    608
...
```

### Step 2: Train the Risk Model

```bash
python risk_model.py
```

**Output:** Trains an XGBoost regressor and saves `model.json` + `zone_base_rate.json`.

**What to expect:**
```
Train rows: 2136  |  Test rows: 724
Test RMSE: 0.1473  |  Test MAE: 0.1171

Feature importances:
  expected_crowd_size       0.1834
  hour_of_day               0.1691
  ...
```

### Step 3: Test the Optimizer (Optional)

```bash
python optimizer.py
```

Runs the CP-SAT solver on a small hardcoded example to verify unit-to-zone assignments.

### Step 4: Test Routing (Optional)

```bash
python routing.py
```

Runs haversine-based route computation on sample reassignments.

### Step 5: Test Scenario Engine (Optional)

```bash
python scenario_engine.py
```

Runs all 4 scenario types (festival, rally, storm, multi-incident) and prints risk spikes + reassignments.

### Step 6: Test Dashboard Metrics (Optional)

```bash
python dashboard_metrics.py
```

Computes optimized vs baseline KPIs for a pitch-ready comparison.

### Step 7: Test Explainability (Optional)

```bash
python explainability.py
```

Generates human-readable risk explanations for different trigger combinations.

### Step 8: Start the API Server

```bash
# Create a main app file (if not already present)
python -c "
from fastapi import FastAPI
from router import router
app = FastAPI(title='SentinelAI Resource Allocation API')
app.include_router(router, prefix='/api')
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=8000)
"
```

Or create a `main.py` file:

```python
from fastapi import FastAPI
from router import router
import uvicorn

app = FastAPI(title="SentinelAI Resource Allocation API")
app.include_router(router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Then run:
```bash
python main.py
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check → `{"status": "ok"}` |
| `GET` | `/api/zones/{zone_id}/risk` | Get risk score for a specific zone |
| `POST` | `/api/optimize` | Run full unit-to-zone optimization |
| `POST` | `/api/simulate` | Run a what-if scenario simulation |

### Example: Get Zone Risk

```bash
curl "http://localhost:8000/api/zones/0/risk?weather_condition=rain&is_event_day=true&expected_crowd_size=5000"
```

### Example: Run Simulation

```bash
curl -X POST "http://localhost:8000/api/simulate" \
  -H "Content-Type: application/json" \
  -d '{"scenario": "festival", "zone_id": 0}'
```

---

## Pipeline Flow

```
1. generate_data.py    →  zones.json, events.json, incidents.csv
                              │
2. risk_model.py       →  model.json, zone_base_rate.json
                              │
3. optimizer.py        →  Assigns units to zones (CP-SAT)
       │
4. routing.py          →  Adds ETA + path to each assignment
       │
5. scenario_engine.py  →  Applies scenario spikes + re-optimizes
       │
6. router.py           →  Exposes everything as REST API
       │
7. dashboard_metrics.py →  Computes KPIs for pitch slides
       │
8. explainability.py   →  Human-readable risk explanations
```

---

## Project Structure

```
Machine Learning/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
│
├── generate_data.py          # Step 1: Synthetic data generation
├── risk_model.py             # Step 2: XGBoost risk model (train + inference)
├── optimizer.py              # Step 3: CP-SAT unit-to-zone assignment
├── routing.py                # Step 4: Route computation (haversine / OSRM)
├── scenario_engine.py        # Step 5: What-if scenario simulations
├── router.py                 # Step 6: FastAPI REST API router
├── dashboard_metrics.py      # Step 7: Optimized vs baseline KPIs
├── explainability.py         # Step 8: Human-readable risk explanations
│
├── zones.json                # Generated: 10 city zones
├── events.json               # Generated: 18 events over 90 days
├── incidents.csv             # Generated: ~3,000 incident records
├── model.json                # Generated: Trained XGBoost model
└── zone_base_rate.json       # Generated: Per-zone baseline risk scores
```

---

## Realism Rules Encoded in Data Generation

| Rule | Implementation |
|------|---------------|
| Zone-specific base rates | Each zone has a fixed Poisson rate (some zones are busier) |
| Late-night spike | Assault/disturbance rates ×2.5 between 22:00–04:00 |
| Afternoon medical bump | Medical emergency ×1.4 during 14:00–22:00 |
| Weekend effect | Disturbance and accident rates ×1.3 on Sat/Sun |
| Weather impact | Rain ×1.3, Storm ×2.0 for accident and medical emergency |
| Event multiplier | Event days ×2–4 (linearly scaled by crowd size 500→15,000) |
| Severity conditioning | Fire/accident skew severity 3–5; theft skews 1–3 |

---

## Key Design Decisions

1. **Temporal train/test split** — No random shuffling; train on earliest 75% of dates to prevent future data leakage
2. **Separate police/ambulance optimization** — CP-SAT solves independently per unit type
3. **Coverage constraints with slack** — Zones ≥0.6 risk need ≥1 unit; ≥0.85 need ≥2 units (if available)
4. **Fixed random seed (42)** — Full reproducibility across runs
5. **Inference without retraining** — `predict_risk()` loads saved model artifacts; importing the module does NOT trigger training

---

## License

Part of the SentinelAI project. See the root repository for license information.
