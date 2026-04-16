from __future__ import annotations

# 1. Base Identity & Access
from .user import User
from .service_listing import ServiceListing  # The polymorphic bridge

# 2. Healthcare & Blood Services
from .blood_donor import BloodDonor
from .blood_request import BloodRequest
from .healthcare_provider import HealthcareProvider
from .healthcare_request import HealthcareRequest
from .doctor import Doctor

# 3. Logistics & Transport
from .transport_offer import TransportOffer
from .transport_request import TransportRequest

# 4. Infrastructure, Chat & Communication
# ✅ Added 'Message' to ensure the chat relationship works
from .chat import ChatRoom, Message
from .call_session import CallSession
from .usage_counter import UsageCounter

# 5. Financials & Orchestration
from .payment import Payment, PaymentStatus

# ---------------------------------------------------------
# ✅ EXPLICIT EXPORTS (Fixes "Cannot find reference" errors)
# ---------------------------------------------------------
__all__ = [
    "User",
    "ServiceListing",
    "BloodDonor",
    "BloodRequest",
    "HealthcareProvider",
    "HealthcareRequest",
    "TransportOffer",
    "TransportRequest",
    "ChatRoom",
    "Message",  # ✅ Required for Chat Relationship indexing
    "Doctor",
    "Payment",
    "PaymentStatus",
    "UsageCounter",
    "CallSession",
]