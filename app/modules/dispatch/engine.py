from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.modules.dispatch.repository import DispatchRepository

logger = logging.getLogger(__name__)


class DispatchEngine:
    """
    AI / rule-based assignment engine.

    Responsibilities:
    - Select best candidate donor/provider
    - Score and rank candidates
    - Decide fallback logic
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
        """
        Core AI decision logic:
        choose best candidate from pre-filtered list.
        """

        if not candidates:
            return {
                "assigned": False,
                "request_id": request_id,
                "donor_id": None,
                "reason": "No candidates available",
            }

        scored = self._score_candidates(candidates)

        best = scored[0]  # already sorted

        donor_id = best.get("donor_id")

        if not donor_id:
            return {
                "assigned": False,
                "request_id": request_id,
                "donor_id": None,
                "reason": "No valid donor found after scoring",
            }

        # Optional: persist assignment (engine-level decision only)
        try:
            if hasattr(self.repository, "mark_assigned"):
                await self.repository.mark_assigned(
                    request_id=request_id,
                    donor_id=donor_id,
                )
        except Exception as exc:
            logger.warning(
                "Failed to persist assignment: %s",
                exc,
            )

        return {
            "assigned": True,
            "request_id": request_id,
            "donor_id": donor_id,
            "score": best.get("score"),
            "eta_minutes": best.get("eta_minutes"),
            "reason": "Best match selected by engine",
        }

    # =========================================================
    # SCORING ENGINE
    # =========================================================

    def _score_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Simple ranking engine.

        You can later replace this with:
        - ML model
        - distance matrix optimization
        - hospital priority rules
        """

        scored = []

        for c in candidates:
            score = self._calculate_score(c)

            scored.append(
                {
                    **c,
                    "score": score,
                }
            )

        # Sort by highest score
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)

        return scored

    def _calculate_score(
        self,
        candidate: Dict[str, Any],
    ) -> float:
        """
        Weighted scoring formula:

        - distance (closer = better)
        - availability (online/ready)
        - urgency match
        - historical reliability (optional)
        """

        distance = float(candidate.get("distance_km") or 999)
        availability = float(candidate.get("availability_score") or 0)
        reliability = float(candidate.get("reliability_score") or 0)
        urgency_match = float(candidate.get("urgency_score") or 0)

        # Simple weighted model (adjust later for ML)
        score = (
            (100 / (1 + distance)) * 0.45 +
            availability * 0.25 +
            reliability * 0.20 +
            urgency_match * 0.10
        )

        return round(score, 4)

    # =========================================================
    # FALLBACK / SAFE MODE LOGIC
    # =========================================================

    async def fallback_assignment(
        self,
        *,
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Used when no candidates exist.
        Can later trigger:
        - nearest hospital escalation
        - admin notification
        """

        return {
            "assigned": False,
            "request_id": request_id,
            "donor_id": None,
            "reason": "Fallback triggered - no candidates",
        }