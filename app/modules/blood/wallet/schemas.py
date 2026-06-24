From __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal, Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =========================================================
# SHARED CONFIG
# =========================================================
def to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        from_attributes=True,
        extra="ignore",
    )


# =========================================================
# WALLET CORE
# =========================================================
class WalletCreate(BaseSchema):
    owner_id: str
    owner_type: Literal["DONOR", "HOSPITAL"]
    currency: str = "XAF"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str):
        return v.upper().strip()


class WalletResponse(BaseSchema):
    id: str
    owner_id: str
    owner_type: Literal["DONOR", "HOSPITAL"]
    balance: Decimal = Decimal("0.00")
    currency: str = "XAF"
    is_active: bool = True
    is_locked: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None


class WalletSummaryResponse(BaseSchema):
    wallet_id: str
    owner_id: str
    owner_type: Literal["DONOR", "HOSPITAL"]
    balance: Decimal
    currency: str
    is_active: bool
    is_locked: bool
    transactions: List[Dict[str, Any]] = []
    payouts: List[Dict[str, Any]] = []


# =========================================================
# WALLET TRANSACTIONS
# =========================================================
class WalletTransactionCreate(BaseSchema):
    owner_id: str
    owner_type: Literal["DONOR", "HOSPITAL"]
    amount: Decimal
    type: Literal["CREDIT", "DEBIT", "WITHDRAWAL", "REFUND", "BONUS", "SURGE"]
    reference_id: Optional[str] = None
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class WalletTransactionResponse(BaseSchema):
    id: str
    wallet_id: str
    type: Literal["CREDIT", "DEBIT", "WITHDRAWAL", "REFUND", "BONUS", "SURGE"]
    amount: Decimal
    reference_id: Optional[str] = None
    description: Optional[str] = None
    status: Literal["pending", "completed", "failed"]
    is_flagged: bool = False
    created_at: datetime


# =========================================================
# PAYOUTS
# =========================================================
class WalletPayoutCreate(BaseSchema):
    owner_id: str
    owner_type: Literal["DONOR"]
    amount: Decimal
    method: Literal["MOBILE_MONEY", "BANK_TRANSFER", "CRYPTO"]
    account_number: str
    account_name: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class WalletPayoutResponse(BaseSchema):
    id: str
    wallet_id: str
    amount: Decimal
    method: Literal["MOBILE_MONEY", "BANK_TRANSFER", "CRYPTO"]
    account_number: str
    account_name: Optional[str] = None
    status: Literal["pending", "approved", "rejected", "paid"]
    processed_by: Optional[str] = None
    requested_at: datetime
    processed_at: Optional[datetime] = None
    is_flagged: bool = False


class WalletPayoutActionResponse(BaseSchema):
    status: str
    payout_id: str
    wallet_id: str
    amount: Decimal
    message: Optional[str] = None


# =========================================================
# BILLING
# =========================================================
class WalletBillingCreate(BaseSchema):
    hospital_id: str
    amount: Decimal
    type: Literal["SUBSCRIPTION", "MATCHING", "PRIORITY_ACCESS"]
    reference_id: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class WalletBillingResponse(BaseSchema):
    id: str
    hospital_id: str
    amount: Decimal
    type: Literal["SUBSCRIPTION", "MATCHING", "PRIORITY_ACCESS"]
    reference_id: Optional[str] = None
    status: Literal["pending", "paid", "failed"]
    created_at: datetime
    paid_at: Optional[datetime] = None


class WalletBillingActionResponse(BaseSchema):
    status: str
    billing_id: str
    hospital_id: str
    amount: Decimal
    message: Optional[str] = None


# =========================================================
# WALLET ACTION REQUESTS
# =========================================================
class CreditWalletRequest(BaseSchema):
    owner_id: str
    owner_type: Literal["DONOR", "HOSPITAL"]
    amount: Decimal
    reference_id: Optional[str] = None
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class DebitWalletRequest(BaseSchema):
    owner_id: str
    owner_type: Literal["DONOR", "HOSPITAL"]
    amount: Decimal
    reference_id: Optional[str] = None
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class SurgeCreditRequest(BaseSchema):
    owner_id: str
    owner_type: Literal["DONOR"]
    amount: Decimal
    reference_id: Optional[str] = None
    description: Optional[str] = "Emergency surge bonus"

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class BonusCreditRequest(BaseSchema):
    owner_id: str
    owner_type: Literal["DONOR", "HOSPITAL"]
    amount: Decimal
    reference_id: Optional[str] = None
    description: Optional[str] = "Bonus credit"

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class RefundRequest(BaseSchema):
    owner_id: str
    owner_type: Literal["DONOR", "HOSPITAL"]
    amount: Decimal
    reference_id: Optional[str] = None
    description: Optional[str] = "Refund"

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


# =========================================================
# API RESPONSE WRAPPERS
# =========================================================
class WalletOperationResponse(BaseSchema):
    status: str
    wallet_id: str
    balance: Decimal
    transaction_id: Optional[str] = None
    credited: Optional[Decimal] = None
    debited: Optional[Decimal] = None


class WalletListResponse(BaseSchema):
    items: List[WalletResponse]
    total: int


class TransactionListResponse(BaseSchema):
    items: List[WalletTransactionResponse]
    total: int


class PayoutListResponse(BaseSchema):
    items: List[WalletPayoutResponse]
    total: int


class BillingListResponse(BaseSchema):
    items: List[WalletBillingResponse]
    total: int