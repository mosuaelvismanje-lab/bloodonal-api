import logging
import os
from fastapi import APIRouter, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring & Analytics"])

# -----------------------------
# 1. RTC & Service Metrics
# -----------------------------

CALL_OUTCOMES_TOTAL = Counter(
    "bloodonal_call_outcomes_total",
    "Total count of call sessions by status and service type",
    ["service_type", "status", "call_mode"],
)

ACTIVE_CALL_SESSIONS = Gauge(
    "bloodonal_active_calls_count",
    "Number of currently active signaling sessions",
    ["service_type"],
)

CALL_DURATION_SECONDS = Histogram(
    "bloodonal_call_duration_seconds",
    "Distribution of successful call durations in seconds",
    ["service_type"],
    buckets=(30, 60, 300, 600, 1200, 1800, 3600),
)

# -----------------------------
# 2. System Health Metrics
# -----------------------------

DB_POOL_CHECKOUTS = Counter(
    "bloodonal_db_pool_checkouts_total",
    "Total times a DB connection was requested",
)

DB_POOL_SIZE = Gauge(
    "bloodonal_db_pool_current_size",
    "Number of connections currently in use",
)

REDIS_LOCK_CONFLICTS = Counter(
    "bloodonal_redis_lock_conflicts_total",
    "Number of times a distributed lock could not be acquired",
    ["lock_type"],
)

# -----------------------------
# 3. Helpers
# -----------------------------

def record_call_event(service_type: str, status: str, call_mode: str):
    CALL_OUTCOMES_TOTAL.labels(service_type, status, call_mode).inc()

    if status == "STARTED":
        ACTIVE_CALL_SESSIONS.labels(service_type).inc()

    elif status in ["COMPLETED", "FAILED", "MISSED"]:
        # Avoid negative values (Prometheus doesn't like it)
        try:
            ACTIVE_CALL_SESSIONS.labels(service_type).dec()
        except ValueError:
            pass


def record_db_usage():
    DB_POOL_CHECKOUTS.inc()


def record_redis_lock_conflict(lock_type: str = "default"):
    REDIS_LOCK_CONFLICTS.labels(lock_type).inc()

# -----------------------------
# 4. Prometheus Endpoint
# -----------------------------

@router.get("/metrics")
async def get_metrics():
    """
    Prometheus metrics endpoint.
    Supports single and multi-worker deployments.
    """
    try:
        multiproc_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")

        # -----------------------------
        # MULTIPROCESS MODE
        # -----------------------------
        if multiproc_dir:
            from prometheus_client import CollectorRegistry, multiprocess

            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            data = generate_latest(registry)

        # -----------------------------
        # SINGLE PROCESS MODE
        # -----------------------------
        else:
            data = generate_latest(REGISTRY)

        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    except Exception as e:
        logger.error(f"Metrics generation failed: {e}", exc_info=True)
        return Response(
            content="# metrics error",
            status_code=500,
            media_type="text/plain",
        )