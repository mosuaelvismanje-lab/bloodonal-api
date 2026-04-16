import re
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ParsedSMS:
    transaction_id: str
    amount: float
    sender: str  # MTN or ORANGE
    raw_body: str

class SMSParser:
    """
    Utility to parse Cameroon Mobile Money SMS strings.
    Extracts Transaction IDs and Amounts for 2026 standardized formats.
    """

    # --- REGEX PATTERNS ---
    # MTN Example: "Transfer confirmed. 500 FCFA sent to... Transaction ID: 2501234567"
    # MTN Cash-in: "You have received 500 FCFA from... TransID: 2501234567"
    MTN_PATTERN = r"(?:Transaction ID|TransID):\s*(\d{10,12})"
    MTN_AMOUNT_PATTERN = r"(\d+(?:\.\d+)?)\s*FCFA"

    # Orange Example: "Le transfert de 500 FCFA au 69XXXXXXX a réussi. ID: CM26..."
    # Orange Cash-in: "Depot de 500 FCFA reussi. Reference: PP26..."
    ORANGE_PATTERN = r"(?:ID|Reference|Ref):\s*([A-Z0-9]{10,20})"
    ORANGE_AMOUNT_PATTERN = r"(\d+(?:\.\d+)?)\s*FCFA"

    @classmethod
    def parse_mtn(cls, body: str) -> Optional[ParsedSMS]:
        """Parses MTN MoMo Cameroon SMS."""
        tx_id_match = re.search(cls.MTN_PATTERN, body, re.IGNORECASE)
        amount_match = re.search(cls.MTN_AMOUNT_PATTERN, body, re.IGNORECASE)

        if tx_id_match and amount_match:
            return ParsedSMS(
                transaction_id=tx_id_match.group(1),
                amount=float(amount_match.group(1).replace(",", "")),
                sender="MTN",
                raw_body=body
            )
        return None

    @classmethod
    def parse_orange(cls, body: str) -> Optional[ParsedSMS]:
        """Parses Orange Money Cameroon SMS."""
        tx_id_match = re.search(cls.ORANGE_PATTERN, body, re.IGNORECASE)
        amount_match = re.search(cls.ORANGE_AMOUNT_PATTERN, body, re.IGNORECASE)

        if tx_id_match and amount_match:
            return ParsedSMS(
                transaction_id=tx_id_match.group(1),
                amount=float(amount_match.group(1).replace(",", "")),
                sender="ORANGE",
                raw_body=body
            )
        return None

    @classmethod
    def parse_any(cls, body: str) -> Optional[ParsedSMS]:
        """
        Heuristic check to determine provider and extract data.
        Ideal for the Android 'User Consent' payload.
        """
        # Clean up whitespace/newlines from SMS
        clean_body = " ".join(body.split())

        # Try MTN first
        parsed = cls.parse_mtn(clean_body)
        if parsed:
            return parsed

        # Try Orange
        parsed = cls.parse_orange(clean_body)
        if parsed:
            return parsed

        logger.warning(f"Failed to parse SMS body: {body[:50]}...")
        return None