import uuid
import time


def generate_tx_id(prefix: str = "tx") -> str:
    """
    Generate a unique transaction ID combining prefix, timestamp, and UUID.
    Example: tx-1700000000-550e8400-e29b-41d4-a716-446655440000
    """
    ts = int(time.time())
    uid = uuid.uuid4()
    return f"{prefix}-{ts}-{uid}"
