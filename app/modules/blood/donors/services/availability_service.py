from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.blood.donors.models import BloodDonor


class AvailabilityService:
    """
    Production-grade donor availability & medical safety service.

    RESPONSIBILITIES:
    - Enforce 90-day donation cooldown rule
    - Determine donor eligibility
    - Compute availability state (stateless logic)
    - Support API, scheduler, and matching engine

    ARCHITECTURE RULES:
    - NO DB commits (repository responsibility)
    - NO side-effect persistence
    - PURE business logic layer
    - TIMEZONE SAFE (UTC only)
    """

    # =========================
    # MEDICAL RULE
    # =========================
    COOLDOWN_DAYS = 90

    # =========================================================
    # CORE ELIGIBILITY CHECK
    # =========================================================
    def is_eligible(self, donor: BloodDonor) -> bool:
        """
        Returns True if donor is medically eligible to donate.
        """

        if not donor.is_active:
            return False

        if not donor.last_donation_date:
            return True

        now = datetime.now(timezone.utc)

        return (now - donor.last_donation_date) >= timedelta(
            days=self.COOLDOWN_DAYS
        )

    # =========================================================
    # SINGLE DONOR STATUS UPDATE (PURE LOGIC)
    # =========================================================
    def update_donor_status(self, donor: BloodDonor) -> BloodDonor:
        """
        Updates donor availability flag based on eligibility rules.
        (No DB operations performed here)
        """

        donor.is_available = self.is_eligible(donor)
        return donor

    # =========================================================
    # SAFETY GATE (BEFORE DONATION)
    # =========================================================
    def can_donate_now(self, donor: BloodDonor) -> bool:
        """
        Final validation before accepting donation.
        """

        return self.is_eligible(donor)

    # =========================================================
    # COOLDOWN ACTIVATION (POST DONATION)
    # =========================================================
    def apply_cooldown(self, donor: BloodDonor) -> BloodDonor:
        """
        Marks donor as inactive after donation and starts cooldown period.
        """

        donor.last_donation_date = datetime.now(timezone.utc)
        donor.is_available = False
        return donor

    # =========================================================
    # BULK REFRESH (SCHEDULER USE ONLY)
    # =========================================================
    def refresh_all_donors(self, db: Session) -> int:
        """
        Recalculates donor availability in bulk.

        NOTE:
        - Still no commit responsibility in production design
        - Caller decides commit/rollback
        """

        donors = db.query(BloodDonor).all()
        updated_count = 0

        for donor in donors:
            old_state = donor.is_available

            donor.is_available = self.is_eligible(donor)

            if donor.is_available != old_state:
                updated_count += 1

        return updated_count