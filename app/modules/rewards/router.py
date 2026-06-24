from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_current_user
from app.modules.blood.domain.ai.reward_optimizer import RewardOptimizer
from app.modules.blood.security.fraud_detection import FraudDetector
from app.modules.blood.wallet.repository import WalletRepository

from app.modules.rewards.service import RewardService
from app.modules.rewards.worker.reward_request import RewardRequest
from app.modules.rewards.worker.reward_worker import RewardWorker

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/rewards",
    tags=["Rewards"],
)


class InMemoryIdempotencyStore:
    """
    Temporary local idempotency store.

    Replace with Redis/database-backed storage for multi-instance production.
    """

    def __init__(self) -> None:
        self._keys: set[str] = set()

    async def exists(self, key: str) -> bool:
        return key in self._keys

    async def save(self, key: str) -> None:
        self._keys.add(key)


# =========================================================
# 🔐 AUTH GUARD
# =========================================================
def require_user(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


# =========================================================
# 🧠 DEPENDENCY BUILDER (SERVICE FACTORY)
# =========================================================
def get_reward_service(db: AsyncSession = Depends(get_db_session)):
    """
    Centralized dependency builder for reward system.
    Ensures consistent initialization across endpoints.
    """

    wallet_repo = WalletRepository()
    fraud_detector = FraudDetector()
    reward_optimizer = RewardOptimizer()

    return RewardService(
        db=db,
        wallet_repo=wallet_repo,
        fraud_detector=fraud_detector,
        reward_optimizer=reward_optimizer,
        reward_worker=RewardWorker(
            db=db,
            wallet_repo=wallet_repo,
            fraud_detector=fraud_detector,
            reward_optimizer=reward_optimizer,
        ),
        idempotency_store=InMemoryIdempotencyStore(),
    )


# =========================================================
# 🔧 PAYLOAD HELPERS
# =========================================================
def _get_value(payload: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


def _get_decimal(payload: Dict[str, Any], *keys: str, default: Any = "0") -> Decimal:
    raw = _get_value(payload, *keys, default=default)
    try:
        return Decimal(str(raw))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decimal value for {keys[0]}",
        ) from exc


def _build_reward_request(payload: Dict[str, Any], user) -> RewardRequest:
    """
    Builds a strict RewardRequest from incoming payload.

    Supports both snake_case and camelCase keys where useful.
    """
    wallet_id = _get_value(payload, "wallet_id", "walletId")
    if wallet_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: wallet_id",
        )

    base_amount = _get_decimal(
        payload,
        "base_amount",
        "baseAmount",
        "incentive_amount",
        "incentiveAmount",
        default="0",
    )

    req = RewardRequest(
        user_id=user.id,
        wallet_id=wallet_id,
        base_amount=base_amount,
        is_urgent=bool(_get_value(payload, "is_urgent", "isUrgent", default=False)),
        same_city=bool(_get_value(payload, "same_city", "sameCity", default=False)),
        exact_blood_match=bool(
            _get_value(payload, "exact_blood_match", "exactBloodMatch", default=False)
        ),
        response_minutes=_get_value(payload, "response_minutes", "responseMinutes"),
        donor_points=int(_get_value(payload, "donor_points", "donorPoints", default=0)),
        total_donations=int(_get_value(payload, "total_donations", "totalDonations", default=0)),
        successful_responses=int(
            _get_value(payload, "successful_responses", "successfulResponses", default=0)
        ),
        rejection_count=int(_get_value(payload, "rejection_count", "rejectionCount", default=0)),
        incentive_amount=_get_decimal(
            payload,
            "incentive_amount",
            "incentiveAmount",
            default=base_amount,
        ),
        request_units=int(_get_value(payload, "request_units", "requestUnits", default=1)),
        hospital_priority_level=int(
            _get_value(payload, "hospital_priority_level", "hospitalPriorityLevel", default=0)
        ),
        active_donors=int(_get_value(payload, "active_donors", "activeDonors", default=0)),
        required_donors=int(_get_value(payload, "required_donors", "requiredDonors", default=0)),
        phone=_get_value(payload, "phone"),
        reference=_get_value(payload, "reference"),
        payment_reference=_get_value(payload, "payment_reference", "paymentReference"),
        context=_get_value(payload, "context", default=None),
    )

    return req


# =========================================================
# 💰 PROCESS REWARD (MAIN PAYOUT ENDPOINT)
# =========================================================
@router.post("/process", response_model=Dict[str, Any])
async def process_reward(
    payload: Dict[str, Any],
    user=Depends(require_user),
    service: RewardService = Depends(get_reward_service),
):
    """
    Main reward execution endpoint.

    Flow:
    --------------------------------
    1. Build reward context
    2. AI scoring (RewardOptimizer)
    3. Fraud detection
    4. Async payout (RewardWorker)
    5. Wallet credit update
    """
    try:
        req = _build_reward_request(payload, user)
        result = await service.process_reward(req)
        return result

    except HTTPException:
        raise

    except KeyError as e:
        logger.warning("Missing field in reward request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field: {str(e)}",
        )

    except Exception as e:
        logger.exception("Reward processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reward processing failed",
        ) from e


# =========================================================
# 🔍 PREVIEW REWARD (NO PAYMENT)
# =========================================================
@router.post("/preview", response_model=Dict[str, Any])
async def preview_reward(
    payload: Dict[str, Any],
    user=Depends(require_user),
    service: RewardService = Depends(get_reward_service),
):
    """
    Safe preview endpoint.

    Shows:
    - reward points
    - wallet credit
    - surge multiplier
    - donor label

    WITHOUT triggering payout.
    """
    try:
        req = _build_reward_request(payload, user)
        return await service.preview_reward(req)

    except HTTPException:
        raise

    except KeyError as e:
        logger.warning("Missing field in reward preview request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field: {str(e)}",
        )

    except Exception as e:
        logger.exception("Reward preview failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reward preview failed",
        ) from e


# =========================================================
# 📊 HEALTH CHECK (REWARD SYSTEM)
# =========================================================
@router.get("/health")
async def reward_health():
    return {
        "status": "ok",
        "module": "rewards",
    }