import logging
from fastapi import APIRouter, Response
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY,
    CollectorRegistry, multiprocess
)
from app.config import settings

# ✅ Standardized logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring & Analytics"])

# -----------------------------
# 1. RTC & Service Metrics
# -----------------------------
CALL_OUTCOMES_TOTAL = Counter(
    "bloodonal_call_outcomes_total",
    "Total count of call sessions by status and service type",
    ["service_type", "status", "call_mode"]
)

ACTIVE_CALL_SESSIONS = Gauge(
    "bloodonal_active_calls_count",
    "Number of currently active signaling sessions",
    ["service_type"]
)

CALL_DURATION_SECONDS = Histogram(
    "bloodonal_call_duration_seconds",
    "Distribution of successful call durations in seconds",
    ["service_type"],
    buckets=(30, 60, 300, 600, 1200, 1800, 3600)
)

# -----------------------------
# 2. System Health & Scaling Metrics
# -----------------------------
DB_POOL_CHECKOUTS = Counter(
    "bloodonal_db_pool_checkouts_total",
    "Total times a DB connection was requested"
)

# New: Track current pool connections (requires hooking into your engine)
DB_POOL_SIZE = Gauge(
    "bloodonal_db_pool_current_size",
    "Number of connections currently in use"
)

REDIS_LOCK_CONFLICTS = Counter(
    "bloodonal_redis_lock_conflicts_total",
    "Number of times a distributed lock could not be acquired",
    ["lock_type"]
)


# -----------------------------
# 3. Metric Update Helpers (Refined)
# -----------------------------

def record_call_event(service_type: str, status: str, call_mode: str):
    CALL_OUTCOMES_TOTAL.labels(service_type, status, call_mode).inc()

    # State tracking
    if status == "STARTED":
        ACTIVE_CALL_SESSIONS.labels(service_type).inc()
    elif status in ["COMPLETED", "FAILED", "MISSED"]:
        # Safety: Ensure we don't drop below 0
        ACTIVE_CALL_SESSIONS.labels(service_type).dec()


def record_db_usage(checkout: bool = True):
    DB_POOL_CHECKOUTS.inc()
    # Note: You need to hook this into your DB engine listeners


# -----------------------------
# 4. Prometheus Scrape Endpoint
# -----------------------------

@router.get("/metrics")
async def get_metrics():
    """
    Exposes metrics for Prometheus.
    Supports multiprocess mode if scaling beyond 1 worker.
    """
    try:
        # If using Gunicorn/Uvicorn multi-worker, REGISTRY needs aggregation
        data = generate_latest(REGISTRY)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Metrics generation failed: {e}")
        return Response(status_code=500)