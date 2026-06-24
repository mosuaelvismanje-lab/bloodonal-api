from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.blood.donors.exceptions import DonorNotFoundError
from app.modules.blood.donors.models import BloodDonor
from app.modules.blood.donors.service import DonorService

logger = logging.getLogger(__name__)


# =========================================================
# EXCEPTIONS
# =========================================================
class DonationOrchestratorError(Exception):
    """Base orchestrator error."""


class DonationOrchestratorValidationError(DonationOrchestratorError):
    """Invalid input provided."""


class DonationOrchestratorStateError(DonationOrchestratorError):
    """Invalid state transition."""


# =========================================================
# ORCHESTRATOR
# =========================================================
class DonationOrchestrator:
    """
    Enterprise-grade donation workflow coordinator.

    Responsibilities:
    - Coordinate donation completion
    - Keep transaction ownership outside the orchestrator
    - Delegate business rules to DonorService
    - Return the updated donor object
    - Keep the flow async-safe
    """

    def __init__(self, donor_service: DonorService):
        self.donors = donor_service
        self._validate_dependencies()

    # =========================================================
    # VALIDATION
    # =========================================================
    def _validate_dependencies(self) -> None:
        if self.donors is None:
            raise DonationOrchestratorValidationError(
                "DonorService is required"
            )

        required_methods = (
            "mark_donation_complete",
        )

        for method in required_methods:
            if not hasattr(self.donors, method):
                raise DonationOrchestratorValidationError(
                    f"DonorService must implement '{method}'"
                )

    def _require_donor_id(self, donor_id: str) -> str:
        if not isinstance(donor_id, str):
            raise DonationOrchestratorValidationError(
                "donor_id must be a string"
            )

        donor_id = donor_id.strip()
        if not donor_id:
            raise DonationOrchestratorValidationError(
                "donor_id cannot be empty"
            )

        return donor_id

    # =========================================================
    # MAIN FLOW
    # =========================================================
    async def complete_donation_flow(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> BloodDonor:
        """
        Finalizes donation workflow.

        Transaction boundary is owned by the caller.
        This method does NOT commit or rollback.
        """
        donor_id = self._require_donor_id(donor_id)

        try:
            donor = await self.donors.mark_donation_complete(
                db,
                donor_id,
            )

            if not donor:
                raise DonationOrchestratorStateError(
                    "Donation flow completed without donor result"
                )

            logger.info(
                "donation_completed",
                extra={
                    "donor_id": donor_id,
                    "status": "completed",
                },
            )

            return donor

        except DonorNotFoundError:
            logger.warning(
                "donation_flow_donor_not_found",
                extra={
                    "donor_id": donor_id,
                    "status": "not_found",
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "donation_flow_failed",
                extra={
                    "donor_id": donor_id,
                    "error": str(exc),
                    "status": "failed",
                },
            )
            raise DonationOrchestratorError(
                f"Donation flow failed for donor {donor_id}"
            ) from exc