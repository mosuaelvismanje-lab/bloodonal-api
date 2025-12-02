import uuid
from typing import Optional, Dict

# Simple in-memory store for idempotency keys.
# For production, use Redis or DB table to persist across restarts.
IDEMPOTENCY_STORE: Dict[str, str] = {}


def generate_idempotency_key() -> str:
    """Generate a new UUID-based idempotency key."""
    return str(uuid.uuid4())


def store_idempotency_key(key: str, user_id: str) -> None:
    """Store key associated with user/service."""
    IDEMPOTENCY_STORE[key] = user_id


def get_user_by_idempotency_key(key: str) -> Optional[str]:
    """Return user_id if key exists, else None."""
    return IDEMPOTENCY_STORE.get(key)
