from __future__ import annotations

import re
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# =========================================================
# DTO
# =========================================================
@dataclass
class ParsedSMS:
    transaction_id: str
    amount: float
    sender: str
    raw_body: str


# =========================================================
# PARSER
# =========================================================
class SMSParser:
    """
    Enterprise-grade SMS parser for Cameroon Mobile Money.

    Guarantees:
    - Safe parsing (no crashes)
    - Provider auto-detection
    - Structured logging
    - Clean normalization
    """

    # =========================
    # REGEX PATTERNS
    # =========================
    MTN_PATTERN = r"(?:Transaction ID|TransID):\s*(\d{10,12})"
    MTN_AMOUNT_PATTERN = r"([\d,]+(?:\.\d+)?)\s*FCFA"

    ORANGE_PATTERN = r"(?:ID|Reference|Ref):\s*([A-Z0-9]{8,20})"
    ORANGE_AMOUNT_PATTERN = r"([\d,]+(?:\.\d+)?)\s*FCFA"

    # =========================
    # NORMALIZATION
    # =========================
    @staticmethod
    def _normalize_body(body: str) -> str:
        """Remove noise, normalize whitespace."""
        return " ".join(body.strip().split())

    @staticmethod
    def _safe_amount(value: str) -> float:
        """Convert string to float safely."""
        try:
            return float(value.replace(",", ""))
        except Exception:
            return 0.0

    # =========================
    # MTN PARSER
    # =========================
    @classmethod
    def parse_mtn(cls, body: str) -> Optional[ParsedSMS]:
        tx_match = re.search(cls.MTN_PATTERN, body, re.IGNORECASE)
        amount_match = re.search(cls.MTN_AMOUNT_PATTERN, body, re.IGNORECASE)

        if not tx_match or not amount_match:
            return None

        parsed = ParsedSMS(
            transaction_id=tx_match.group(1),
            amount=cls._safe_amount(amount_match.group(1)),
            sender="MTN",
            raw_body=body,
        )

        logger.info(
            "sms_parsed_mtn",
            extra={
                "tx_id": parsed.transaction_id,
                "amount": parsed.amount,
            },
        )

        return parsed

    # =========================
    # ORANGE PARSER
    # =========================
    @classmethod
    def parse_orange(cls, body: str) -> Optional[ParsedSMS]:
        tx_match = re.search(cls.ORANGE_PATTERN, body, re.IGNORECASE)
        amount_match = re.search(cls.ORANGE_AMOUNT_PATTERN, body, re.IGNORECASE)

        if not tx_match or not amount_match:
            return None

        parsed = ParsedSMS(
            transaction_id=tx_match.group(1),
            amount=cls._safe_amount(amount_match.group(1)),
            sender="ORANGE",
            raw_body=body,
        )

        logger.info(
            "sms_parsed_orange",
            extra={
                "tx_id": parsed.transaction_id,
                "amount": parsed.amount,
            },
        )

        return parsed

    # =========================
    # UNIVERSAL PARSER
    # =========================
    @classmethod
    def parse_any(cls, body: str) -> Optional[ParsedSMS]:
        """
        Auto-detect provider and parse SMS.

        Flow:
        1. Normalize
        2. Try MTN
        3. Try Orange
        4. Log failure safely
        """

        if not body or not body.strip():
            logger.warning(
                "sms_parse_empty_body",
                extra={"body": body},
            )
            return None

        clean_body = cls._normalize_body(body)

        # Try MTN
        parsed = cls.parse_mtn(clean_body)
        if parsed:
            return parsed

        # Try Orange
        parsed = cls.parse_orange(clean_body)
        if parsed:
            return parsed

        # Failure (structured log)
        logger.warning(
            "sms_parse_failed",
            extra={
                "preview": clean_body[:80],
            },
        )

        return None