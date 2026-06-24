from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Final, Mapping, Optional

from .constants import VALID_BLOOD_GROUPS


# =========================================================
# IMMUTABLE BLOOD COMPATIBILITY MAP (AUDIT SAFE)
# =========================================================
_BLOOD_COMPATIBILITY_RAW: dict[str, frozenset[str]] = {
    "O-": frozenset({"O-"}),
    "O+": frozenset({"O-", "O+"}),
    "A-": frozenset({"O-", "A-"}),
    "A+": frozenset({"O-", "O+", "A-", "A+"}),
    "B-": frozenset({"O-", "B-"}),
    "B+": frozenset({"O-", "O+", "B-", "B+"}),
    "AB-": frozenset({"O-", "A-", "B-", "AB-"}),
    "AB+": frozenset({"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"}),
}

BLOOD_COMPATIBILITY: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    _BLOOD_COMPATIBILITY_RAW
)

DONATION_COOLDOWN_DAYS: Final[int] = 90

EXACT_MATCH_PRIORITY_BOOST: Final[int] = 30
UNIVERSAL_DONOR_PRIORITY_BOOST: Final[int] = 20


# =========================================================
# NORMALIZATION
# =========================================================
def normalize_group(group: Optional[str]) -> str:
    if group is None or not isinstance(group, str):
        return ""

    value = group.strip().upper()
    if not value:
        return ""

    return value if value in VALID_BLOOD_GROUPS else ""


def is_valid_blood_group(group: Optional[str]) -> bool:
    return normalize_group(group) in VALID_BLOOD_GROUPS


# =========================================================
# MEDICAL ELIGIBILITY
# =========================================================
def is_eligible_to_donate(
    last_donation_date: Optional[datetime],
    reference_date: Optional[datetime] = None,
) -> bool:
    if last_donation_date is None:
        return True

    if not isinstance(last_donation_date, datetime):
        raise TypeError("last_donation_date must be a datetime or None")

    if reference_date is not None and not isinstance(reference_date, datetime):
        raise TypeError("reference_date must be a datetime or None")

    now = reference_date or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if last_donation_date.tzinfo is None:
        last_donation_date = last_donation_date.replace(tzinfo=timezone.utc)

    if last_donation_date > now:
        raise ValueError("Corrupted timestamp: last_donation_date is in the future")

    return (now - last_donation_date) >= timedelta(days=DONATION_COOLDOWN_DAYS)


def next_eligible_date(last_donation_date: Optional[datetime]) -> Optional[datetime]:
    if last_donation_date is None:
        return None

    if not isinstance(last_donation_date, datetime):
        raise TypeError("last_donation_date must be a datetime or None")

    if last_donation_date.tzinfo is None:
        last_donation_date = last_donation_date.replace(tzinfo=timezone.utc)

    return last_donation_date + timedelta(days=DONATION_COOLDOWN_DAYS)


# =========================================================
# COMPATIBILITY RULES
# =========================================================
def is_compatible(
    request_blood_group: str,
    donor_blood_group: str,
) -> bool:
    request = normalize_group(request_blood_group)
    donor = normalize_group(donor_blood_group)

    if not request or not donor:
        return False

    return donor in BLOOD_COMPATIBILITY.get(request, frozenset())


def is_exact_match(
    request_blood_group: str,
    donor_blood_group: str,
) -> bool:
    request = normalize_group(request_blood_group)
    donor = normalize_group(donor_blood_group)

    if not request or not donor:
        return False

    return request == donor


def is_universal_donor(donor_blood_group: str) -> bool:
    return normalize_group(donor_blood_group) == "O-"


# =========================================================
# FINAL ELIGIBILITY GATE
# =========================================================
def is_donor_eligible(
    donor_blood_group: str,
    request_blood_group: str,
    last_donation_date: Optional[datetime],
) -> bool:
    if not is_compatible(request_blood_group, donor_blood_group):
        return False

    return is_eligible_to_donate(last_donation_date)


# =========================================================
# PRIORITY BOOST SIGNALS
# =========================================================
def get_priority_boost(
    donor_blood_group: str,
    request_blood_group: str,
) -> int:
    if is_exact_match(request_blood_group, donor_blood_group):
        return EXACT_MATCH_PRIORITY_BOOST

    if is_universal_donor(donor_blood_group):
        return UNIVERSAL_DONOR_PRIORITY_BOOST

    return 0