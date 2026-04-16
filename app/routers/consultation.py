import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Production Standard: Secure identity and database session
from app.api.dependencies import get_current_user, get_db_session
from app.domain.usecases import ConsultationUseCase
from app.domain.consultation_models import RequestResponse, ChannelType, UserRoles

# ✅ Infrastructure: Using updated repository paths
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.infrastructure.jitsi import JitsiGateway
from app.gateways.mtn_momo_adapter import MockAdapter
from app.adapters.chat_gateway import DummyChatGateway

logger = logging.getLogger(__name__)

# ✅ Versioning: Prefix set to /v1/consultation for production API standards
router = APIRouter(prefix="/v1/consultation", tags=["consultation"])


async def get_consultation_usecase(
        session: AsyncSession = Depends(get_db_session),
) -> ConsultationUseCase:
    """
    Dependency provider for the Consultation UseCase.
    In production, swap MockAdapter for real MTN/Orange Momo Gateways.
    """
    usage_repo = SQLAlchemyUsageRepository(session)
    payment_gateway = MockAdapter()
    call_gateway = JitsiGateway()
    chat_gateway = DummyChatGateway()

    return ConsultationUseCase(
        usage_repo=usage_repo,
        payment_gateway=payment_gateway,
        call_gateway=call_gateway,
        chat_gateway=chat_gateway,
    )


@router.post(
    "/{channel_type}/{recipient_id}/{recipient_role}",
    response_model=RequestResponse,
    status_code=status.HTTP_200_OK,
)
async def start_consultation(
        channel_type: ChannelType,
        recipient_id: str,
        recipient_role: UserRoles,
        phone_number: Annotated[str, Query(..., description="User's MoMo number")],
        use_case: Annotated[ConsultationUseCase, Depends(get_consultation_usecase)],
        db: AsyncSession = Depends(get_db_session),
        # ✅ Production Security: user_id is extracted from the Firebase JWT
        current_user=Depends(get_current_user),
        amount: Annotated[int, Query(description="Payment amount")] = 500,
        idempotency_key: Annotated[Optional[str], Query(description="Unique idempotency key")] = None,
) -> RequestResponse:
    """
    🚀 Production Logic Flow:
    1. Validates User Identity via Bearer Token.
    2. Ensures a UsageCounter exists for the authenticated UID.
    3. Executes the UseCase (checks free quota -> handles payment -> returns Jitsi link).
    4. Commits the transaction to persist usage counts.
    """
    user_id = current_user.uid

    try:
        # ✅ JIT Provisioning: Ensure user exists in the usage_counters table
        usage_repo = SQLAlchemyUsageRepository(db)
        await usage_repo.get_or_create_counter(user_id)

        # ✅ Execute Business Logic
        result: RequestResponse = await use_case.handle(
            caller_id=user_id,
            recipient_id=recipient_id,
            caller_phone=phone_number,
            channel=channel_type,
            recipient_role=recipient_role,
            amount=float(amount),
            idempotency_key=idempotency_key or f"cons-{uuid.uuid4().hex[:12]}"
        )

        # ✅ Persistence: Commit changes (usage increment) to Neon Postgres
        await db.commit()
        return result

    except ConsultationUseCase.FreeQuotaExceeded as e:
        logger.info(f"Free quota exceeded for {user_id}: {e}")
        # 402 is the industry standard for payment required
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e)
        )

    except Exception as exc:
        # ✅ Rollback: Ensure data integrity on failure
        await db.rollback()
        logger.exception(f"Consultation failed for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the consultation."
        )