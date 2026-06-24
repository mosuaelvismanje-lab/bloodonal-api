from __future__ import annotations
from enum import Enum


class UserRole(str, Enum):
    """
    =========================================================
    PLATFORM USER ROLES (GLOBAL AUTHORIZATION LAYER)
    =========================================================
    """

    # CORE USERS
    USER = "user"
    DONOR = "donor"
    PATIENT = "patient"

    # MEDICAL PROVIDERS
    DOCTOR = "doctor"
    NURSE = "nurse"
    LAB_TECH = "lab_tech"

    # TRANSPORT PROVIDERS
    TAXI = "taxi"
    BIKE = "bike"
    AMBULANCE = "ambulance"

    # ORGANIZATIONS
    HOSPITAL = "hospital"
    BLOOD_BANK = "blood_bank"

    # ADMINISTRATION
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"