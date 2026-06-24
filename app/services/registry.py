from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings


# ---------------------------------------------------------
# ✅ DYNAMIC SERVICE REGISTRY (ENTERPRISE / 2026 UPDATE)
# ---------------------------------------------------------
#
# Responsibilities:
# - Centralize service metadata
# - Resolve fees and free tiers
# - Respect global and per-service payment switches
# - Flag realtime/RTC-enabled services
# - Support dispatch/live-map related services
# - Expose a stable manifest for frontend/admin use
#
# This registry is intentionally data-driven so it stays
# consistent with backend settings and future service growth.
# ---------------------------------------------------------


class ServiceRegistry:
    """
    Business logic layer for service metadata.

    Keeps a cached manifest of:
    - service display name
    - fee information
    - free limits
    - payment availability
    - realtime / RTC eligibility
    - category classification
    """

    def __init__(self) -> None:
        self._services: Dict[str, Dict[str, Any]] = {}
        self.refresh_registry()

    # =========================================================
    # REGISTRY BUILD
    # =========================================================

    def refresh_registry(self) -> None:
        """
        Rebuild the internal service manifest from settings.

        Falls back safely if configuration keys are missing.
        """
        fee_map = getattr(settings, "fee_map", {}) or {}
        for key in self._default_service_keys():
            if key not in fee_map:
                fee_map[key] = 0

        self._services = {
            key: self.get_service_meta(key)
            for key in fee_map.keys()
        }

    def _default_service_keys(self) -> List[str]:
        """
        Service keys that should always exist in the manifest,
        even if not yet present in fee_map.
        """
        return [
            "blood",
            "blood-donation",
            "blood-request",
            "healthcare",
            "consultation",
            "doctor",
            "nurse",
            "transport",
            "ambulance",
            "pharmacy",
            "lab",
            "dispatch",
            "dispatch-nearby",
            "dispatch-live",
        ]

    # =========================================================
    # METADATA
    # =========================================================

    @staticmethod
    def get_service_meta(service_key: str) -> Dict[str, Any]:
        """
        Build metadata for a service key.

        This is designed to remain stable for:
        - admin dashboards
        - mobile UI
        - billing rules
        - dispatch routing
        - realtime eligibility
        """
        normalized_key = (service_key or "").strip().lower()
        display_name = normalized_key.replace("-", " ").title()

        rtc_supported_list = getattr(
            settings,
            "RTC_SERVICES",
            ["doctor", "nurse", "consultation", "telemedicine"],
        ) or []

        # Global app switches and maps are optional; default safely.
        fee_map = getattr(settings, "fee_map", {}) or {}
        free_limits = getattr(settings, "free_limits", {}) or {}
        payment_switches = getattr(settings, "payment_switches", {}) or {}
        promo_messages = getattr(settings, "promo_messages", {}) or {}

        is_rtc_eligible = normalized_key in rtc_supported_list

        return {
            "key": normalized_key,
            "display_name": display_name,
            "base_fee": int(fee_map.get(normalized_key, 0) or 0),
            "free_limit": int(free_limits.get(normalized_key, 0) or 0),
            "is_enabled": bool(payment_switches.get(normalized_key, True)),
            "is_payment_globally_enabled": bool(
                getattr(settings, "PAYMENT_ENABLED", True)
            ),
            "promo_message": str(promo_messages.get(normalized_key, "") or ""),
            "quota_type": normalized_key.replace("-", "_"),
            "is_rtc_supported": is_rtc_eligible,
            "category": ServiceRegistry._get_category(normalized_key),
            "is_dispatch_supported": ServiceRegistry._is_dispatch_service(normalized_key),
            "is_live_map_supported": ServiceRegistry._is_dispatch_service(normalized_key),
        }

    @staticmethod
    def _is_dispatch_service(service_key: str) -> bool:
        """
        Detect dispatch/live-map style services.
        """
        key = (service_key or "").strip().lower()
        return (
            key == "dispatch"
            or key.startswith("dispatch-")
            or key in {"transport", "ambulance", "blood", "blood-request"}
        )

    @staticmethod
    def _get_category(service_key: str) -> str:
        """
        Classify services for admin reports and frontend grouping.
        """
        key = (service_key or "").strip().lower()

        if key in {"blood", "blood-request", "blood-donation"}:
            return "medical"

        if key in {"doctor", "nurse", "consultation", "healthcare", "lab", "pharmacy"}:
            return "medical"

        if key in {"transport", "ambulance"}:
            return "logistics"

        if key.startswith("dispatch-") or key == "dispatch":
            return "dispatch"

        return "general"

    # =========================================================
    # FEE ENGINE
    # =========================================================

    def calculate_effective_fee(
        self,
        service_key: str,
        current_usage_count: int,
        duration_minutes: int = 0,
    ) -> int:
        """
        Calculate the final payable fee.

        Rules:
        - disabled service => free
        - global payment off => free
        - free limit not reached => free
        - RTC services may use per-minute billing
        """
        meta = self._services.get(
            service_key,
            self.get_service_meta(service_key),
        )

        if not meta["is_enabled"] or not meta["is_payment_globally_enabled"]:
            return 0

        if current_usage_count < meta["free_limit"]:
            return 0

        if meta["is_rtc_supported"] and duration_minutes > 0:
            per_minute_rate = int(
                getattr(settings, "fee_map", {}).get(
                    f"{service_key}-per-minute",
                    0,
                ) or 0
            )
            return int(meta["base_fee"]) + (per_minute_rate * duration_minutes)

        return int(meta["base_fee"])

    # =========================================================
    # PUBLIC ACCESSORS
    # =========================================================

    def get_all_services_manifest(self) -> Dict[str, Dict[str, Any]]:
        """
        Return full cached service manifest.
        """
        return self._services

    def get_service(self, service_key: str) -> Dict[str, Any]:
        """
        Safe fetch for a single service.
        """
        key = (service_key or "").strip().lower()
        return self._services.get(key, self.get_service_meta(key))

    def get_enabled_services(self) -> List[Dict[str, Any]]:
        """
        Return only services that are currently enabled.
        """
        return [
            meta for meta in self._services.values()
            if meta.get("is_enabled", False) and meta.get("is_payment_globally_enabled", True)
        ]

    def get_services_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Filter services by category:
        - medical
        - logistics
        - dispatch
        - general
        """
        normalized = (category or "").strip().lower()
        return [
            meta for meta in self._services.values()
            if meta.get("category") == normalized
        ]

    def is_service_enabled(self, service_key: str) -> bool:
        """
        Check whether a specific service is enabled.
        """
        meta = self.get_service(service_key)
        return bool(meta.get("is_enabled", False)) and bool(
            meta.get("is_payment_globally_enabled", True)
        )

    def is_rtc_supported(self, service_key: str) -> bool:
        """
        Check whether a service supports realtime/RTC.
        """
        meta = self.get_service(service_key)
        return bool(meta.get("is_rtc_supported", False))

    def is_dispatch_supported(self, service_key: str) -> bool:
        """
        Check whether a service should participate in the dispatch engine.
        """
        meta = self.get_service(service_key)
        return bool(meta.get("is_dispatch_supported", False))

    def to_frontend_manifest(self) -> Dict[str, Dict[str, Any]]:
        """
        Frontend-safe manifest with only fields the UI needs.
        """
        manifest: Dict[str, Dict[str, Any]] = {}

        for key, meta in self._services.items():
            manifest[key] = {
                "key": meta["key"],
                "display_name": meta["display_name"],
                "base_fee": meta["base_fee"],
                "free_limit": meta["free_limit"],
                "is_enabled": meta["is_enabled"],
                "promo_message": meta["promo_message"],
                "category": meta["category"],
                "is_rtc_supported": meta["is_rtc_supported"],
                "is_dispatch_supported": meta["is_dispatch_supported"],
            }

        return manifest

    def get_payment_summary(self) -> Dict[str, Any]:
        """
        Aggregated overview for admin dashboards.
        """
        total = len(self._services)
        enabled = len(self.get_enabled_services())

        categories: Dict[str, int] = {}
        for meta in self._services.values():
            category = str(meta.get("category", "general"))
            categories[category] = categories.get(category, 0) + 1

        return {
            "total_services": total,
            "enabled_services": enabled,
            "disabled_services": total - enabled,
            "payment_enabled": bool(getattr(settings, "PAYMENT_ENABLED", True)),
            "categories": categories,
        }

    # =========================================================
    # MAINTENANCE
    # =========================================================

    def clear_cache(self) -> None:
        """
        Clear and rebuild cache.
        """
        self._services.clear()
        self.refresh_registry()

    def upsert_service(self, service_key: str) -> Dict[str, Any]:
        """
        Force insert/update a single service in cache.
        Useful when settings are hot-reloaded.
        """
        key = (service_key or "").strip().lower()
        meta = self.get_service_meta(key)
        self._services[key] = meta
        return meta


# ✅ Singleton registry for app-wide use
registry = ServiceRegistry()