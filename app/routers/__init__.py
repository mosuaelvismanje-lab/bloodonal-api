"""
Central router export module.
Synchronized for Async flow and Geo-free models.
"""

import logging

logger = logging.getLogger(__name__)

# =====================================================
# PAYMENT ROUTERS
# =====================================================
from .bike_payment import router as bike_payment_router
from .webhook_payment import router as webhook_payment_router

# Optional bike service helpers (safe fallback)
try:
    from .bike_payment import (
        get_remaining_free_uses as bike_get_remaining_free_uses,
        process_payment as bike_process_payment,
    )
except ImportError:
    bike_get_remaining_free_uses = None
    bike_process_payment = None

# ✅ IMPORTANT:
# Removed incorrect router aliasing (was breaking logic & tests)
# DO NOT map unrelated services to bike router


# =====================================================
# BLOOD MODULES
# =====================================================
from .blood_donor import router as blood_donor_router
from .blood_request import router as blood_request_router

# Safe legacy aliases (only for backward compatibility)
blood_payment_router = blood_request_router
blood_payments_router = blood_request_router


# =====================================================
# HEALTHCARE / CONSULTATION
# =====================================================
from .health_provider import router as healthcare_providers_router
from .health_request import router as healthcare_requests_router

# Aliases (intentional + safe)
consultation_router = healthcare_requests_router
doctors_router = healthcare_providers_router


# =====================================================
# COMMUNICATION MODULES
# =====================================================
try:
    from .call import router as calls_router
except ImportError:
    logger.warning("⚠️ call router not available")
    calls_router = None

try:
    from .chat import router as chat_router
except ImportError:
    logger.warning("⚠️ chat router not available")
    chat_router = None


# =====================================================
# TRANSPORT MODULES (Geo-Free)
# =====================================================
from .transport_offer import router as transport_offer_router
from .transport_request import router as transport_request_router


# =====================================================
# FINAL EXPORTS
# =====================================================
__all__ = [
    # =========================
    # PAYMENTS
    # =========================
    "bike_payment_router",
    "webhook_payment_router",
    "bike_get_remaining_free_uses",
    "bike_process_payment",

    # =========================
    # BLOOD
    # =========================
    "blood_donor_router",
    "blood_request_router",
    "blood_payment_router",
    "blood_payments_router",

    # =========================
    # HEALTHCARE
    # =========================
    "healthcare_providers_router",
    "healthcare_requests_router",
    "consultation_router",
    "doctors_router",

    # =========================
    # COMMUNICATION
    # =========================
    "calls_router",
    "chat_router",

    # =========================
    # TRANSPORT
    # =========================
    "transport_offer_router",
    "transport_request_router",
]