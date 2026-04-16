from fastapi import APIRouter, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY
)
from app.config import settings

router = APIRouter(prefix="/monitoring", tags=["Monitoring & Analytics"])

# -----------------------------
# 1. RTC & Service Metrics
# -----------------------------

# Track total call attempts vs outcomes
CALL_OUTCOMES_TOTAL = Counter(
    "bloodonal_call_outcomes_total",
    "Total count of call sessions by status and service type",
    ["service_type", "status", "call_mode"]
)

# Track active signals (Gauge is better for "current state")
ACTIVE_CALL_SESSIONS = Gauge(
    "bloodonal_active_calls_count",
    "Number of currently active signaling sessions in Redis",
    ["service_type"]
)

# Track how long successful calls actually last
CALL_DURATION_SECONDS = Histogram(
    "bloodonal_call_duration_seconds",
    "Distribution of successful call durations in seconds",
    ["service_type"],
    buckets=(30, 60, 300, 600, 1200, 1800, 3600)
)

# -----------------------------
# 2. System Health Metrics (New for 2026 Scaling)
# -----------------------------

# Track DB Pool Saturation (Crucial since we increased to 291+)
DB_POOL_CHECKOUTS = Counter(
    "bloodonal_db_pool_checkouts_total",
    "Total times a DB connection was requested from the pool"
)

# Track Redis Lock failures (indicates race conditions/concurrency issues)
REDIS_LOCK_CONFLICTS = Counter(
    "bloodonal_redis_lock_conflicts_total",
    "Number of times a distributed lock could not be acquired",
    ["lock_type"]  # e.g., 'service_accept', 'wallet_update'
)


# -----------------------------
# 3. Metric Update Helpers
# -----------------------------

def record_call_event(service_type: str, status: str, call_mode: str):
    CALL_OUTCOMES_TOTAL.labels(
        service_type=service_type,
        status=status,
        call_mode=call_mode
    ).inc()

    # Adjust active gauge based on status
    if status == "STARTED":
        ACTIVE_CALL_SESSIONS.labels(service_type=service_type).inc()
    elif status in ["COMPLETED", "FAILED", "MISSED"]:
        ACTIVE_CALL_SESSIONS.labels(service_type=service_type).dec()


def record_lock_conflict(lock_type: str):
    """Call this in the 'if not is_locked' blocks of your routers."""
    REDIS_LOCK_CONFLICTS.labels(lock_type=lock_type).inc()


def record_call_duration(service_type: str, duration: int):
    if duration > 0:
        CALL_DURATION_SECONDS.labels(service_type=service_type).observe(duration)


# -----------------------------
# 4. Prometheus Scrape Endpoint
# -----------------------------

@router.get("/metrics")
def get_metrics():
    """
    Exposes metrics for Prometheus scraping.
    """
    # Optional: Include logic here to sample DB pool status directly from the engine
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)