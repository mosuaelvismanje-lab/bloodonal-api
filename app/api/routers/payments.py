# File: app/api/routers/payments.py

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.domain.usecases import (
    SERVICE_FEES,
    SERVICE_FREE_LIMITS,
    ConsultationUseCase,
)
from app.api.dependencies import get_current_user, get_db_session
from app.data.repositories import UsageRepository
from app.adapters import mtn, orange

router = APIRouter(prefix="/v1/payments", tags=["payments"])


class RemainingWithFeeResponse(BaseModel):
    remaining: int
    fee: int


class PaymentResponseOut(BaseModel):
    service: str
    transaction_id: str


@router.get(
    "/{service}/remaining",
    response_model=RemainingWithFeeResponse,
    summary="Get how many free uses remain and the fee for a service"
)
async def get_remaining_with_fee(
    service: str,
    user=Depends(get_current_user),
    db=Depends(get_db_session),
):
    # 1) validate that the service exists
    if service not in SERVICE_FEES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service!r} not found. Valid: {list(SERVICE_FEES.keys())}"
        )

    # 2) compute how many times the user has already used it
    usage_repo = UsageRepository(db)
    used       = await usage_repo.count(user.uid, service)

    # 3) compute remaining free uses
    free_limit = SERVICE_FREE_LIMITS.get(service, 0)
    remaining  = max(0, free_limit - used)

    # 4) look up the fee for paid usage
    fee = SERVICE_FEES[service]

    return RemainingWithFeeResponse(remaining=remaining, fee=fee)


@router.post(
    "/{service}",
    response_model=PaymentResponseOut,
    summary="Consume a free slot or charge for the given service"
)
async def pay_service(
    service: str,
    phone: str,
    user=Depends(get_current_user),
    db=Depends(get_db_session),
):
    # validate that the service exists
    if service not in SERVICE_FEES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service!r} not found. Valid: {list(SERVICE_FEES.keys())}"
        )

    # pick the appropriate gateway adapter
    gateway = mtn if service in ("taxi", "bike") else orange

    # construct and run the use‑case
    uc = ConsultationUseCase(
        usage_repo=UsageRepository(db),
        gateway=gateway
    )

    try:
        tx_id = await uc.handle(user.uid, service, phone)
    except ValueError as e:
        # this should not happen unless service validation failed
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return PaymentResponseOut(service=service, transaction_id=tx_id)
