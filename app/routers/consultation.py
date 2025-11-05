# app/routers/consultation.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.database import get_async_session
from app.api.dependencies import get_current_user_id

from app.domain.usecases import ConsultationUseCase
from app.domain.consultation_models import RequestResponse, ChannelType, UserRoles

from app.infrastructure.repositories import SQLAlchemyUsageRepository
from app.infrastructure.jitsi import JitsiGateway
from app.adapters.mtn_gateway import MtnGateway
from app.adapters.chat_gateway import DummyChatGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consultation", tags=["consultation"])


async def get_consultation_usecase(
    session: AsyncSession = Depends(get_async_session),
) -> ConsultationUseCase:
    """
    Dependency that constructs a ConsultationUseCase wired with concrete adapters/repositories.
    The AsyncSession is provided by get_async_session and its lifecycle is managed by FastAPI.
    """
    usage_repo = SQLAlchemyUsageRepository(session)
    payment_gateway = MtnGateway()
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
    phone_number: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    use_case: ConsultationUseCase = Depends(get_consultation_usecase),
) -> RequestResponse:
    """
    Start a consultation using the provided consultation use case.
    - channel_type: enum (e.g., AUDIO, VIDEO)
    - recipient_id: id of recipient (doctor, nurse, etc.)
    - recipient_role: recipient role enum
    - phone_number: caller's phone number (string)
    - user_id: injected from auth dependency
    """
    try:
        # Expect that use_case.handle is async and returns a RequestResponse
        result: RequestResponse = await use_case.handle(
            caller_id=user_id,
            recipient_id=recipient_id,
            caller_phone=phone_number,
            channel=channel_type,
            recipient_role=recipient_role,
        )
        return result

    except ConsultationUseCase.FreeQuotaExceeded as e:
        # Business-level error — user exceeded free quota
        logger.info("Free quota exceeded for user %s: %s", user_id, str(e))
        # Return a structured failure response rather than HTTP error (keeps client flow consistent)
        return RequestResponse(success=False, message=str(e))

    except ConsultationUseCase.NotFoundError as e:
        # If the use case raises a not-found domain error, return 404
        logger.warning("Consultation target not found: %s (user=%s)", recipient_id, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except Exception as exc:
        # Unexpected errors => log and return 500
        logger.exception("Unexpected error while starting consultation (user=%s)", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to start consultation at this time",
        ) from exc
