from __future__ import annotations

from typing import Final

VALID_BLOOD_GROUPS: Final[frozenset[str]] = frozenset({
    "O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"
})