# app/schemas/__init__.py

from .payment import (
    PaymentRequest,
    PaymentResponse,
    PaymentStatus,      # ✅ Added for central access
    FreeUsageResponse,
)

from .doctor_payment import (
    DoctorPaymentRequest,
    DoctorPaymentResponse,
)

from .nurse_payment import (
    NursePaymentRequest,
    NursePaymentResponse,
)

from .bike_payment import (
    BikePaymentRequest,
    BikePaymentResponse,
    BikeFreeUsageResponse,  # ✅ Added to match the bike router's /remaining endpoint
)

from .taxi_payment import (
    TaxiPaymentRequest,
    TaxiPaymentResponse,
)

from .blood_payment import (
    BloodRequestPaymentRequest,
    BloodRequestPaymentResponse,
)
