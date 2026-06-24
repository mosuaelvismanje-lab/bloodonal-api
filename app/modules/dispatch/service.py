from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Dict, List, Optional

from app.modules.blood.domain.constants import VALID_BLOOD_GROUPS
from app.modules.dispatch.repository import DispatchRepository
from app.modules.dispatch.schemas import NearbyRequestDTO

from app.modules.dispatch.engine import DispatchEngine  # ✅ NEW


# =========================================================
# CONTEXT
# =========================================================
@dataclass(slots=True)
class DispatchContext:
    service_type: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: float = 50.0
    blood_group: Optional[str] = None
    limit: int = 200
    include_clusters: bool = False
    cluster_precision_km: float = 1.0


# =========================================================
# SERVICE (ORCHESTRATION LAYER ONLY)
# =========================================================
class DispatchService:
    """
    Responsibilities:
    - Query repository
    - Enrich + rank requests
    - Convert DTOs
    - Cluster map data
    - Delegate AI assignment to engine
    """

    def __init__(self, repository: DispatchRepository):
        self.repository = repository
        self.engine = DispatchEngine(repository)  # ✅ AI ENGINE

    # =========================================================
    # NEARBY REQUESTS
    # =========================================================
    async def get_nearby_requests(
        self,
        context: DispatchContext,
    ) -> List[NearbyRequestDTO]:

        raw = await self.repository.fetch_nearby_requests(
            service_type=context.service_type,
            latitude=context.latitude,
            longitude=context.longitude,
            radius_km=context.radius_km,
            limit=context.limit,
        )

        if not raw:
            return []

        enriched = self._enrich(raw, context)
        ranked = self._rank(enriched)

        if context.include_clusters:
            ranked = self._attach_cluster_hints(ranked, context)

        return [self._to_dto(r) for r in ranked]

    # =========================================================
    # ENRICHMENT
    # =========================================================
    def _enrich(self, items: List[Dict[str, Any]], ctx: DispatchContext):
        enriched = []

        for r in items:
            lat = self._as_float(r.get("latitude"), default=None)
            lng = self._as_float(r.get("longitude"), default=None)

            distance = self._distance(ctx.latitude, ctx.longitude, lat, lng)

            enriched.append({
                **r,
                "distance_km": distance,
                "urgency_score": self._urgency(r),
                "blood_match_score": self._blood_match(
                    r.get("blood_group"),
                    ctx.blood_group,
                ),
                "relevance_score": self._relevance(r, ctx),
            })

        return enriched

    # =========================================================
    # RANKING (NON-AI PREVIEW SORT ONLY)
    # =========================================================
    def _rank(self, items: List[Dict[str, Any]]):
        def score(r: Dict[str, Any]) -> float:
            distance = self._as_float(r.get("distance_km"), default=None)
            proximity = max(0.0, 100.0 - distance) if distance is not None else 0.0

            return (
                float(r.get("urgency_score", 0.0) or 0.0) * 0.40 +
                float(r.get("blood_match_score", 0.0) or 0.0) * 0.30 +
                proximity * 0.20 +
                float(r.get("relevance_score", 0.0) or 0.0) * 0.10
            )

        return sorted(items, key=score, reverse=True)

    # =========================================================
    # CLUSTERING
    # =========================================================
    def _attach_cluster_hints(
        self,
        items: List[Dict[str, Any]],
        ctx: DispatchContext,
    ) -> List[Dict[str, Any]]:

        result = []

        for r in items:
            lat = self._as_float(r.get("latitude"), default=None)
            lng = self._as_float(r.get("longitude"), default=None)

            if lat is None or lng is None:
                result.append({**r, "cluster_id": None, "heat_zone": "unknown"})
                continue

            result.append({
                **r,
                "cluster_id": self._cluster_key(lat, lng, ctx.cluster_precision_km),
                "heat_zone": self._heat_zone(r),
            })

        return result

    # =========================================================
    # URGENCY
    # =========================================================
    def _urgency(self, r: Dict[str, Any]) -> float:
        score = 0.0

        if self._as_bool(r.get("is_urgent")):
            score += 60.0

        score += self._as_float(r.get("hospital_priority_level"), default=0.0) * 5.0

        if self._as_float(r.get("needed_units"), default=0.0) > 3:
            score += 10.0

        return min(score, 100.0)

    # =========================================================
    # BLOOD MATCH
    # =========================================================
    def _blood_match(self, request_blood: Any, donor_blood: Any) -> float:
        req = self._normalize_blood(request_blood)
        donor = self._normalize_blood(donor_blood)

        if not req or not donor:
            return 0.0

        if req == donor:
            return 100.0

        return 85.0 if donor in VALID_BLOOD_GROUPS else 10.0

    # =========================================================
    # RELEVANCE
    # =========================================================
    def _relevance(self, r: Dict[str, Any], ctx: DispatchContext) -> float:
        score = 50.0

        if str(r.get("service_type", "")).lower() == ctx.service_type.lower():
            score += 30.0

        if self._as_bool(r.get("is_urgent")):
            score += 20.0

        return min(score, 100.0)

    # =========================================================
    # DISTANCE (HAVERSINE)
    # =========================================================
    def _distance(self, lat1, lon1, lat2, lon2):
        if None in (lat1, lon1, lat2, lon2):
            return None

        R = 6371.0

        dlat = radians(float(lat2) - float(lat1))
        dlon = radians(float(lon2) - float(lon1))

        a = (
            sin(dlat / 2) ** 2 +
            cos(radians(float(lat1))) *
            cos(radians(float(lat2))) *
            sin(dlon / 2) ** 2
        )

        return 2 * R * atan2(sqrt(a), sqrt(1 - a))

    # =========================================================
    # AI ENGINE DELEGATION (IMPORTANT CHANGE)
    # =========================================================
    async def assign_best_match(
        self,
        request_id: str,
        candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        NOW DELEGATED TO ENGINE
        """
        return await self.engine.assign_best_match(
            request_id=request_id,
            candidates=candidates,
        )

    # =========================================================
    # CLUSTER KEY
    # =========================================================
    def _cluster_key(self, lat: float, lng: float, precision_km: float) -> str:
        p = max(0.01, float(precision_km) / 111.0)
        return f"{round(lat / p)}:{round(lng / p)}"

    def _heat_zone(self, r: Dict[str, Any]) -> str:
        urgency = self._urgency(r)

        if urgency >= 80:
            return "extreme"
        if urgency >= 60:
            return "high"
        if urgency >= 30:
            return "medium"
        return "low"

    # =========================================================
    # NORMALIZERS
    # =========================================================
    def _normalize_blood(self, b: Any):
        if not b:
            return None
        return str(b).upper().strip()

    def _as_float(self, v, default=0.0):
        try:
            return float(v) if v is not None else default
        except Exception:
            return default

    def _as_bool(self, v):
        return bool(v)

    # =========================================================
    # DTO
    # =========================================================
    def _to_dto(self, r: Dict[str, Any]) -> NearbyRequestDTO:
        return NearbyRequestDTO(
            id=str(r.get("id", "")),
            patient_name=r.get("patient_name", "Unknown"),
            blood_group=r.get("blood_group", "Unknown"),
            needed_units=int(r.get("needed_units", 0)),
            city=r.get("city", "Unknown"),
            latitude=float(r.get("latitude", 0.0)),
            longitude=float(r.get("longitude", 0.0)),
            is_urgent=bool(r.get("is_urgent", False)),
            service_type=r.get("service_type", "unknown"),
            distance_km=float(r.get("distance_km", 0.0)),
            urgency_score=float(r.get("urgency_score", 0.0)),
            blood_match_score=float(r.get("blood_match_score", 0.0)),
            relevance_score=float(r.get("relevance_score", 0.0)),
        )