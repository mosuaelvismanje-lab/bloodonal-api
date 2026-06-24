from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.blood.donors.models import BloodDonor


DONATION_COOLDOWN_DAYS = 90  # 3 months


class DonorSchedulerJobs:
    """
    Production background jobs for donor system
    """

    # =========================================================
    # AUTO UPDATE ELIGIBILITY (3 MONTH RULE)
    # =========================================================
    @staticmethod
    def update_donor_availability():
        """
        Automatically updates donor eligibility based on last donation.
        Runs daily.
        """

        db: Session = SessionLocal()
        try:
            donors = db.query(BloodDonor).all()

            now = datetime.utcnow()

            for donor in donors:
                last = donor.last_donation_date

                if not last:
                    donor.is_available = True
                    continue

                days = (now - last).days

                # eligible after 90 days
                donor.is_available = days >= DONATION_COOLDOWN_DAYS

            db.commit()

        finally:
            db.close()

    # =========================================================
    # AUTO RESET INACTIVE DONORS
    # =========================================================
    @staticmethod
    def reset_stale_donors():
        """
        Re-activate inactive donors after long inactivity.
        """

        db: Session = SessionLocal()
        try:
            threshold = datetime.utcnow() - timedelta(days=180)

            donors = db.query(BloodDonor).filter(
                BloodDonor.last_donation_date <= threshold
            ).all()

            for donor in donors:
                donor.is_active = True

            db.commit()

        finally:
            db.close()