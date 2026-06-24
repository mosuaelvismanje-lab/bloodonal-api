from __future__ import annotations

import uuid
import random
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.modules.blood.donors.models import BloodDonor


# =========================================================
# SAFE SEED CONFIG (NO REAL DATA)
# =========================================================
BLOOD_GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
CITIES = ["Buea", "Douala", "Yaounde", "Limbe", "Bamenda"]

NAMES = [
    "John", "Peter", "Samuel", "Grace", "Mary",
    "Daniel", "Victor", "Esther", "Michael", "Rebecca",
]


class SeedDonorService:
    """
    Production-safe seed service.

    PURPOSE:
    - development testing
    - frontend demo (Flutter)
    - fallback system when DB is empty

    IMPORTANT:
    - NEVER used in production live environment (except fallback mode)
    """

    # =========================================================
    # MAIN SEED FUNCTION
    # =========================================================
    def seed(self, db: Session, count: int = 50) -> None:
        """
        Seed fake donors safely into database.
        """

        existing_count = db.query(BloodDonor).count()

        # Prevent duplicate seeding
        if existing_count > 0:
            return

        donors: List[BloodDonor] = []

        for _ in range(count):

            donor = BloodDonor(
                id=str(uuid.uuid4()),
                full_name=self._random_name(),
                phone=self._random_phone(),
                city=random.choice(CITIES),
                blood_group=random.choice(BLOOD_GROUPS),

                is_available=random.choice([True, True, False]),
                is_active=True,

                last_donation_date=self._random_donation_date(),

                fcm_token=f"mock_fcm_{uuid.uuid4().hex[:12]}",

                points=random.randint(0, 500),
                total_donations=random.randint(0, 15),
                successful_responses=random.randint(0, 10),
                rejection_count=random.randint(0, 3),

                rank_level=random.choice(
                    ["Bronze", "Silver", "Gold", "Platinum"]
                ),

                referral_code=uuid.uuid4().hex[:8],
                referred_by=None,

                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            donors.append(donor)

        db.bulk_save_objects(donors)
        db.commit()

    # =========================================================
    # FALLBACK MODE (USED IN MATCHING SERVICE)
    # =========================================================
    def generate_seed_donors(self, city: str, blood_group: str, count: int = 10):
        """
        Returns in-memory donors when DB is empty.
        Used for:
        - testing
        - system bootstrap
        - demo mode
        """

        donors = []

        for _ in range(count):
            donors.append(
                {
                    "id": str(uuid.uuid4()),
                    "full_name": self._random_name(),
                    "phone": self._random_phone(),
                    "city": city,
                    "blood_group": blood_group,
                    "is_available": True,
                    "is_active": True,
                    "fcm_token": f"mock_{uuid.uuid4().hex[:10]}",
                    "points": random.randint(0, 200),
                    "total_donations": random.randint(0, 5),
                    "successful_responses": random.randint(0, 5),
                    "rejection_count": 0,
                    "rank_level": "Bronze",
                    "referral_code": uuid.uuid4().hex[:8],
                    "referred_by": None,
                    "last_donation_date": None,
                }
            )

        return donors

    # =========================================================
    # HELPERS
    # =========================================================
    def _random_name(self) -> str:
        return f"{random.choice(NAMES)} {random.choice(['N.', 'K.', 'M.', 'T.'])}"

    def _random_phone(self) -> str:
        return f"+2376{random.randint(10000000, 99999999)}"

    def _random_donation_date(self):
        # simulate medical safety variability (0–180 days ago)
        return datetime.utcnow() - timedelta(days=random.randint(0, 180))