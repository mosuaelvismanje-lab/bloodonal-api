"""
Central router export module.
Synchronized for Async flow and Geo-free models.
"""
import logging

logger = logging.getLogger(__name__)

# =========================
# PAYMENT-RELATED ROUTERS
# =========================
from .bike_payment import router as bike_payment_router
from .webhook_payment import router as webhook_payment_router

# Aliases for Bike Payment Service Logic
try:
    from .bike_payment import get_remaining_free_uses as bike_get_remaining_free_uses
    from .bike_payment import process_payment as bike_process_payment
except ImportError:
    bike_get_remaining_free_uses = None
    bike_process_payment = None

# Aliases for legacy test compatibility
doctor_payment_router = bike_payment_router
nurse_payment_router = bike_payment_router
taxi_payment_router = bike_payment_router

# =========================
# BLOOD MODULES
# =========================
from .blood_donor import router as blood_donor_router
from .blood_request import router as blood_request_router

# Legacy aliases for blood payments
blood_payment = blood_request_router
blood_payments = blood_request_router

# =========================
# HEALTHCARE / CONSULTATION
# =========================
# ✅ FIXED: Removed '.app.routers' and changed 'routers' to 'router'
from .health_provider import router as healthcare_providers_router
from .health_request import router as healthcare_requests_router

# Aliases for secondary healthcare routers
consultation_router = healthcare_requests_router
doctors_router = healthcare_providers_router

# =========================
# COMMUNICATION
# =========================
try:
    from .call import router as calls_router
    from .chat import router as chat_router
except ImportError:
    calls_router = None
    chat_router = None

# =========================
# TRANSPORT (Geo-Free)
# =========================
from .transport_offer import router as transport_offer_router
from .transport_request import router as transport_request_router

# =========================
# EXPORT LIST
# =========================
__all__ = [
    "bike_payment_router",
    "webhook_payment_router",
    "doctor_payment_router",
    "nurse_payment_router",
    "taxi_payment_router",
    "blood_donor_router",
    "blood_request_router",
    "healthcare_providers_router",
    "healthcare_requests_router",
    "transport_offer_router",
    "transport_request_router",
    "calls_router",
    "chat_router"
]