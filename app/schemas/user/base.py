from pydantic import BaseModel


class BaseSchema(BaseModel):
    """
    =========================================================
    BASE SCHEMA (ENTERPRISE DTO ROOT)
    =========================================================

    Shared behavior for all request/response schemas:
    - future-proof extension point
    - validation consistency layer
    - logging / serialization hooks (optional later)
    =========================================================
    """
    pass