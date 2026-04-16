from typing import Dict, Any, List
from app.config import settings


# ---------------------------------------------------------
# ✅ DYNAMIC SERVICE REGISTRY (2026 Production Update)
# ---------------------------------------------------------

class ServiceRegistry:
    """
    Business Logic layer: Maps internal keys to human-readable names,
    calculates dynamic fees (Fixed vs. Duration), and manages service availability.
    """

    def __init__(self):
        # ✅ Initialize internal storage to prevent 'attribute not found' errors
        self._services = {}
        self.refresh_registry()

    def refresh_registry(self):
        """Builds the internal map from settings.fee_map."""
        # Using a dictionary comprehension to cache all service metadata at startup
        self._services = {key: self.get_service_meta(key) for key in settings.fee_map.keys()}

    @staticmethod
    def get_service_meta(service_key: str) -> Dict[str, Any]:
        """
        Aggregates metadata for a service.
        Detects RTC support and categorizes services for Admin reporting.
        """
        display_name = service_key.replace("-", " ").title()

        # ✅ IMPROVEMENT: Pull RTC eligibility from settings instead of hardcoding
        # settings.RTC_SERVICES should be a list like ['doctor', 'nurse', 'consultation']
        rtc_supported_list = getattr(settings, "RTC_SERVICES", ["doctor", "nurse", "consultation"])
        is_rtc_eligible = service_key in rtc_supported_list

        return {
            "key": service_key,
            "display_name": display_name,
            "base_fee": settings.fee_map.get(service_key, 0),
            "free_limit": settings.free_limits.get(service_key, 0),
            "is_enabled": settings.payment_switches.get(service_key, True),
            # ✅ NEW: Global master switch for the repository to check
            "is_payment_globally_enabled": getattr(settings, "PAYMENT_ENABLED", True),
            "promo_message": settings.promo_messages.get(service_key, ""),
            "quota_type": service_key.replace("-", "_"),
            "is_rtc_supported": is_rtc_eligible,
            "category": "medical" if is_rtc_eligible or "blood" in service_key else "logistics"
        }

    def calculate_effective_fee(
            self,
            service_key: str,
            current_usage_count: int,
            duration_minutes: int = 0
    ) -> int:
        """
        The "Price Engine": Handles Free Tiers, Global Toggles,
        and optional Duration-based billing.
        """
        # Look up in cached services, fallback to dynamic fetch if not cached
        meta = self._services.get(service_key, self.get_service_meta(service_key))

        # If the specific service or global payment is disabled, fee is 0
        if not meta["is_enabled"] or not meta["is_payment_globally_enabled"]:
            return 0

        # Check if user is still within their free quota
        if current_usage_count < meta["free_limit"]:
            return 0

        # Handle Per-Minute Billing for Telemedicine/RTC
        if meta["is_rtc_supported"] and duration_minutes > 0:
            per_minute_rate = settings.fee_map.get(f"{service_key}-per-minute", 0)
            return meta["base_fee"] + (per_minute_rate * duration_minutes)

        return meta["base_fee"]

    def get_all_services_manifest(self) -> Dict[str, Dict[str, Any]]:
        """Returns the full cached manifest for the Mobile UI."""
        return self._services


# ✅ Instantiate as a singleton for use across the app
registry = ServiceRegistry()