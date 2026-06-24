from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.modules.dispatch.repository import DispatchRepository

logger = logging.getLogger(__name__)


class DispatchEngine:
    """
    AI / rule-based assignment engine.

    Responsibility:
    - Score candidates
    - Select best match
    - Handle fallback logic
    - Optional persistence decision (via repository)
    """

    def __init__(self, repository: DispatchRepository):
        self.repository = repository

    # =========================================================
    # MAIN ENTRY POINT
    # =========================================================
    async def assign_best_match(
        self,
        *,
        request_id: str,
        candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        if not candidates:
            return self._fallback(request_id, "No candidates available")

        scored = self._score_candidates(candidates)

        if not scored:
            return self._fallback(request_id, "Scoring produced no results")

        best = scored[0]
        donor_id = best.get("donor_id")

        if not donor_id:
            return self._fallback(request_id, "Invalid best candidate")

        # Optional persistence (safe fail)
        await self._persist_assignment(request_id, donor_id)

        return {
            "assigned": True,
            "request_id": request_id,
            "donor_id": donor_id,
            "score": best.get("score"),
            "eta_minutes": best.get("eta_minutes"),
            "reason": "Best match selected by DispatchEngine",
        }

    # =========================================================
    # SCORING ENGINE
    # =========================================================
    def _score_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        scored = []

        for c in candidates:
            score = self._calculate_score(c)

            scored.append({
                **c,
                "score": score,
            })

        return sorted(scored, key=lambda x: x.get("score", 0), reverse=True)

    def _calculate_score(self, c: Dict[str, Any]) -> float:
        """
        Simple weighted AI scoring model
        (replace later with ML model)
        """

        distance = float(c.get("distance_km") or 999)
        availability = float(c.get("availability_score") or 0)
        reliability = float(c.get("reliability_score") or 0)
        urgency = float(c.get("urgency_score") or 0)

        score = (
            (100 / (1 + distance)) * 0.45 +
            availability * 0.25 +
            reliability * 0.20 +
            urgency * 0.10
        )

        return round(score, 4)

    # =========================================================
    # PERSISTENCE (SAFE OPTIONAL)
    # =========================================================
    async def _persist_assignment(self, request_id: str, donor_id: str) -> None:
        try:
            if hasattr(self.repository, "mark_assigned"):
                await self.repository.mark_assigned(
                    request_id=request_id,
                    donor_id=donor_id,
                )
        except Exception as exc:
            logger.warning("Assignment persistence failed: %s", exc)

    # =========================================================
    # FALLBACK LOGIC
    # =========================================================
    def _fallback(self, request_id: str, reason: str) -> Dict[str, Any]:
        return {
            "assigned": False,
            "request_id": request_id,
            "donor_id": None,
            "reason": reason,
        }