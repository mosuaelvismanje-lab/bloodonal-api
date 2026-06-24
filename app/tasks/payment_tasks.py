from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.exc import (
    DBAPIError,
    OperationalError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)

# =========================================================
# CONFIG
# =========================================================

WORKER_SLEEP_SECONDS = 300  # 5 min

REPORT_HOUR_UTC = 23
REPORT_MINUTE_UTC = 59

MAX_FAILURE_BACKOFF = 300

# =========================================================
# HELPERS
# =========================================================


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _should_run_daily_report(
    now: datetime,
    last_run: Optional[datetime],
) -> bool:
    """
    Execute once per day.
    """

    if (
        now.hour != REPORT_HOUR_UTC
        or now.minute != REPORT_MINUTE_UTC
    ):
        return False

    if last_run is None:
        return True

    return now.date() > last_run.date()


def _safe_metric(
    metrics: Dict[str, Any],
    key: str,
    default: int = 0,
) -> int:
    value = metrics.get(key, default)

    try:
        return int(value)

    except (TypeError, ValueError):
        return default


# =========================================================
# DAILY REPORT
# =========================================================


async def send_daily_platform_report() -> Dict[str, Any]:
    """
    Generate platform metrics report.
    """

    try:
        async with AsyncSessionLocal() as db:  # type: AsyncSession

            metrics = await StatsService.get_dashboard_metrics(
                db
            )

            report_date = (
                _now_utc() - timedelta(days=1)
            ).strftime("%Y-%m-%d")

            result = {
                "date": report_date,
                "total_revenue": _safe_metric(
                    metrics,
                    "total_revenue_today",
                ),
                "bypass_matches": _safe_metric(
                    metrics,
                    "bypass_matches_today",
                ),
                "awaiting_verification": _safe_metric(
                    metrics,
                    "total_awaiting_verification",
                ),
                "mtn_volume": _safe_metric(
                    metrics,
                    "mtn_volume",
                ),
                "orange_volume": _safe_metric(
                    metrics,
                    "orange_volume",
                ),
            }

            logger.info(
                "daily_platform_report_generated",
                extra=result,
            )

            return result

    except (
        TimeoutError,
        asyncio.TimeoutError,
        ConnectionError,
        DBAPIError,
        OperationalError,
    ) as exc:

        logger.warning(
            "daily_platform_report_db_unavailable",
            extra={
                "error": str(exc),
            },
        )

        return {}

    except Exception as exc:

        logger.exception(
            "daily_platform_report_failed",
            extra={
                "error": str(exc),
            },
        )

        return {}


# =========================================================
# WORKER LOOP
# =========================================================


async def run_payment_worker_loop() -> None:
    """
    Enterprise background worker.

    Responsibilities:
        - Payment cleanup
        - Daily reporting
        - Self-healing retries
        - Never crash
    """

    from app.tasks.payment_janitor import (
        expire_unconfirmed_payments,
    )

    last_report_run: Optional[datetime] = None

    consecutive_failures = 0

    logger.info(
        "payment_worker_started",
    )

    while True:

        try:
            now = _now_utc()

            # ==========================================
            # PAYMENT JANITOR
            # ==========================================

            pending_count, stale_count = (
                await expire_unconfirmed_payments()
            )

            if pending_count or stale_count:
                logger.info(
                    "payment_cleanup_executed",
                    extra={
                        "pending_expired": pending_count,
                        "stale_expired": stale_count,
                    },
                )

            # ==========================================
            # DAILY REPORT
            # ==========================================

            if _should_run_daily_report(
                now,
                last_report_run,
            ):
                await send_daily_platform_report()
                last_report_run = now

            # ==========================================
            # HEALTH LOG
            # ==========================================

            logger.debug(
                "payment_worker_heartbeat",
                extra={
                    "timestamp": now.isoformat(),
                },
            )

            consecutive_failures = 0

            await asyncio.sleep(
                WORKER_SLEEP_SECONDS
            )

        except (
            TimeoutError,
            asyncio.TimeoutError,
            ConnectionError,
            DBAPIError,
            OperationalError,
        ) as exc:

            consecutive_failures += 1

            backoff = min(
                consecutive_failures * 10,
                MAX_FAILURE_BACKOFF,
            )

            logger.warning(
                "payment_worker_database_unavailable",
                extra={
                    "error": str(exc),
                    "retry_in_seconds": backoff,
                    "consecutive_failures": (
                        consecutive_failures
                    ),
                },
            )

            await asyncio.sleep(backoff)

        except Exception as exc:

            consecutive_failures += 1

            backoff = min(
                consecutive_failures * 10,
                MAX_FAILURE_BACKOFF,
            )

            logger.exception(
                "worker_loop_failure",
                extra={
                    "error": str(exc),
                    "retry_in_seconds": backoff,
                    "consecutive_failures": (
                        consecutive_failures
                    ),
                },
            )

            await asyncio.sleep(backoff)