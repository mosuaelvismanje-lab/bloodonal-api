# =========================================================
# FILE: app/utils/geo_utils.py
# =========================================================

from __future__ import annotations

import math
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


# =========================================================
# CONSTANTS
# =========================================================
EARTH_RADIUS_KM: float = 6371.0


# =========================================================
# CORE NORMALIZATION
# =========================================================
def normalize_coordinates(
    latitude: float,
    longitude: float,
) -> Tuple[float, float]:
    """
    Validates and normalizes geo coordinates.
    """

    lat = round(float(latitude), 6)
    lng = round(float(longitude), 6)

    if not -90 <= lat <= 90:
        raise ValueError(f"Invalid latitude: {lat}")

    if not -180 <= lng <= 180:
        raise ValueError(f"Invalid longitude: {lng}")

    return lat, lng


# =========================================================
# DISTANCE CALCULATION (HAVERSINE)
# =========================================================
def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculates distance between two geo points using Haversine formula.
    Returns distance in kilometers.
    """

    lat1, lon1 = normalize_coordinates(lat1, lon1)
    lat2, lon2 = normalize_coordinates(lat2, lon2)

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return round(EARTH_RADIUS_KM * c, 2)


# =========================================================
# WITHIN RADIUS CHECK
# =========================================================
def within_radius(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    radius_km: float,
) -> bool:
    """
    Checks if two points are within a given radius.
    """
    return haversine_distance_km(lat1, lon1, lat2, lon2) <= radius_km


# =========================================================
# SAFE WRAPPER (FIX FOR YOUR IMPORT ERROR)
# =========================================================
def safe_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Safe distance calculation that never raises exceptions.
    Returns 0.0 if invalid input.
    """

    try:
        return haversine_distance_km(lat1, lon1, lat2, lon2)
    except Exception as exc:
        logger.warning("safe_distance_km failed: %s", exc)
        return 0.0