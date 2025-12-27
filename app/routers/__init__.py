"""
Central router export module.

Purpose:
- Make all routers importable via `app.routers.<name>`
- Provide backward-compatible aliases for tests (doctor_payments, blood_payments, etc.)
- Avoid ModuleNotFoundError during pytest monkeypatching
"""

# =========================
# PAYMENT-RELATED ROUTERS
# =========================

from .bike_payment import router as bike_payment_router
from .bike_payment import (
    get_remaining_free_uses as bike_get_remaining_free_uses,
    process_payment as bike_process_payment,
)

from .webhook_payment import router as webhook_payment_router

# ---- Aliases expected by tests ----
# (tests refer to doctor_payments / blood_payments even if files differ)
from .doctor_payments import router as doctor_payment_router
from .nurse_payments import router as nurse_payment_router
from .taxi_payment import router as taxi_payment_router

# =========================
# BLOOD MODULES
# =========================

from .blood_donor import router as blood_donor_router
from .blood_request import router as blood_request_router
from .blood_request_payments import router as blood_request_payment_router

# Aliases for historical test imports
blood_payment = blood_request_router
blood_payments = blood_request_router

# =========================
# HEALTHCARE / CONSULTATION
# =========================

from .consultation import router as consultation_router
from .doctors import router as doctors_router

from .health_provider import router as healthcare_providers_router
from .health_request import router as healthcare_requests_router

# =========================
# COMMUNICATION
# =========================

from .call import router as calls_router
from .chat import router as chat_router
from .notifications import router as notifications_router

# =========================
# TRANSPORT
# =========================

from .transport_offer import router as transport_offer_router
from .transport_request import router as transport_request_router

# =========================
# EXPORT LIST (optional)
# =========================

__all__ = [
    # payments
    "bike_payment_router",
    "webhook_payment_router",
    "doctor_payment_router",
    "nurse_payment_router",
    "taxi_payment_router",

    # blood
    "blood_donor_router",
    "blood_request_router",
    "blood_request_payment_router",

    # consultation / healthcare
    "consultation_router",
    "doctors_router",
    "healthcare_providers_router",
    "healthcare_requests_router",

    # communication
    "calls_router",
    "chat_router",
    "notifications_router",

    # transport
    "transport_offer_router",
    "transport_request_router",
]
