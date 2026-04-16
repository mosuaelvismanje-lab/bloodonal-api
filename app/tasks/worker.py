import os
import redis
import logging
import sys
import signal
from rq import Worker, Queue

# 1. Path Fix: Ensure the worker can see 'app' module
sys.path.append(os.getcwd())

# 2. Configure logging with 2026 Audit Format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("worker")

# 3. Setup Redis Connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
LISTEN = ["payments", "default"]

# ---------------------------------------------------------
# Task Pre-loading (Critical for Modular Logic)
# ---------------------------------------------------------
try:
    # Importing here ensures the worker process has the code in memory
    from app.tasks.payment_tasks import expire_unconfirmed_payments
    logger.info("📦 Payment tasks pre-loaded into worker context.")
except ImportError as e:
    logger.error(f"❌ Failed to load tasks: {e}. Check PYTHONPATH.")

def run_worker():
    """
    Initializes and starts the RQ Worker using Direct Injection.
    """
    try:
        # High-reliability connection settings
        conn = redis.from_url(
            REDIS_URL,
            health_check_interval=30,
            socket_connect_timeout=10,
            retry_on_timeout=True
        )
        conn.ping()
        logger.info("✅ Connected to Redis successfully.")

    except redis.exceptions.ConnectionError as e:
        logger.error("❌ Fatal: Could not connect to Redis: %s", e)
        sys.exit(1)

    # Direct Connection Injection
    queues = [Queue(name, connection=conn) for name in LISTEN]

    # Worker configuration
    worker_id = f"worker-bloodonal-{os.getpid()}"
    worker = Worker(queues, name=worker_id, connection=conn)

    logger.info("🚀 RQ Worker [%s] active. Listening for Payments & Default tasks.", worker_id)

    # 'with_scheduler=True' allows the worker to process the Cron-like
    # 'expire_unconfirmed_payments' task automatically.
    worker.work(with_scheduler=True)


# ---------------------------------------------------------
# Lifecycle Management (Graceful Shutdown)
# ---------------------------------------------------------
def shutdown_handler(sig, frame):
    """Gracefully handles termination for Docker/Kubernetes/Neon."""
    logger.info("🛑 Worker received termination signal. Cleaning up current jobs...")
    # Add any specific cleanup logic here (e.g., closing open DB pools)
    sys.exit(0)


if __name__ == "__main__":
    # Register signals
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    run_worker()