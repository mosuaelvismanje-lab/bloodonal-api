import logging
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services.stats_service import StatsService
from app.services.registry import registry

logger = logging.getLogger(__name__)


# ----------------------------
# 1. Daily Summary Report Task
# ----------------------------
async def send_daily_platform_report():
    """
    Cron Task: Runs at midnight to summarize the day's performance.
    Uses StatsService for math and Registry for service names.
    """
    async with AsyncSessionLocal() as db:
        try:
            # 1. Fetch Metrics for the last 24 hours
            metrics = await StatsService.get_dashboard_metrics(db)

            # 2. Build a Human-Readable Message
            report_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

            summary_lines = [
                f"📊 *Platform Report: {report_date}*",
                f"💰 Total Revenue: {metrics['total_revenue_today']} XAF",
                f"🤖 Auto-Verified (Bypass): {metrics['bypass_matches_today']}",
                f"⏳ Pending Review: {metrics['total_awaiting_verification']}",
                "---------------------------",
                f"📶 MTN Volume: {metrics.get('mtn_volume', 0)} XAF",
                f"📶 Orange Volume: {metrics.get('orange_volume', 0)} XAF"
            ]

            # 3. Optional: Add Service Breakdown
            # (e.g., 'Blood Request: 15 uses')
            # For this, you'd use registry.get_service_meta to get names

            full_report = "\n".join(summary_lines)

            # 4. Dispatch (Telegram/Slack/Email)
            # await notify_owners(full_report)
            logger.info(f"📈 Daily Report Generated:\n{full_report}")

        except Exception as e:
            logger.error(f"💥 Failed to generate daily report: {str(e)}")


# ----------------------------
# 2. Background Worker Integration
# ----------------------------
async def run_payment_worker_loop():
    """
    Main loop for the background worker.
    Combines the Janitor (Cleanup) and Reporting.
    """
    while True:
        # Import the cleanup task from your file
        from .payment_janitor import expire_unconfirmed_payments

        # Run Cleanup every 5 minutes
        await expire_unconfirmed_payments()

        # logic to run reporting only once a day at 23:59...

        await asyncio.sleep(300)  # Sleep for 5 minutes