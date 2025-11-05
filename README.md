# Bloodonal FastAPI Backend

## Overview
Backend for Bloodonal app: blood donation, healthcare requests, transport, symptom reporting, outbreak alerts, vaccination campaigns, plus a public-health API layer.

## Setup
1. Copy `.env` and fill in DB credentials.
2. `pip install -r requirements.txt`
3. Run: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
4. The OpenAPI docs are at `/docs`.

## Endpoints
- `/donors`, `/blood-requests`, `/healthcare-providers`, etc.
- `/symptom-reports`, `/outbreaks`, `/vaccination/...`
- Public API under `/public/...`

## Deployment
- Deploy on Cloud Run or another host; ensure `.env` variables are set.
