from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.api.response import error
from app.modules.blood.donors.exceptions import DonorDomainError


async def donor_exception_handler(request: Request, exc: DonorDomainError):
    return JSONResponse(
        status_code=400,
        content=error(
            message=exc.message,
            error_code=exc.code
        )
    )