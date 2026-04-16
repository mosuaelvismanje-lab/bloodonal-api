from __future__ import annotations

import logging
from typing import List, Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, update
from app.models.blood_request import BloodRequest
from app.schemas.blood_requests import BloodRequestCreate

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# CREATE: ATOMIC STAGING
# -------------------------------------------------------------------------

async def create_blood_request(
        db: AsyncSession,
        req: BloodRequestCreate,
        user_id: str
) -> BloodRequest:
    """
    Stages a new blood request record.

    ✅ ATOMICITY: Uses db.flush() to get ID/Timestamps without committing,
    allowing the Service Orchestrator to commit both this and Usage records together.
    """
    try:
        # 1. Convert Schema to dict and filter for DB columns
        obj_data = req.model_dump()
        model_columns = {column.name for column in BloodRequest.__table__.columns}
        filtered_data = {k: v for k, v in obj_data.items() if k in model_columns}

        # 2. Inject ownership and system defaults
        filtered_data["user_id"] = user_id
        filtered_data["status"] = "PENDING"  # Always start as pending

        # 3. Initialize SQLAlchemy object
        db_obj = BloodRequest(**filtered_data)

        # 4. Stage changes
        db.add(db_obj)

        # 5. Push to DB to generate ID/Timestamps, but DO NOT commit yet.
        # This allows the background task to use the ID before the final commit.
        await db.flush()
        await db.refresh(db_obj)

        logger.debug(f"CRUD: Staged Blood Request {db_obj.id} for user {user_id}")
        return db_obj

    except Exception as e:
        logger.error(f"CRUD Error (create): {str(e)}")
        raise e


# -------------------------------------------------------------------------
# READ: GLOBAL FEED & LOOKUP
# -------------------------------------------------------------------------

async def get_blood_requests(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = "PENDING"
) -> Sequence[BloodRequest]:
    """
    Fetches requests for the global feed.
    Sorting: Urgent (🚨) first, then newest created_at.
    """
    try:
        query = select(BloodRequest)

        # Apply status filter if provided (Defaults to PENDING for feed)
        if status_filter:
            query = query.where(BloodRequest.status == status_filter)

        # 2026 Sorting Logic: Prioritize high-urgency cases for the Limbe/Southwest region
        query = query.order_by(
            desc(BloodRequest.urgent),
            desc(BloodRequest.created_at)
        )

        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        # Unique prevents duplicate objects in joined loads
        return result.scalars().unique().all()

    except Exception as e:
        logger.error(f"CRUD Error (get_all): {e}")
        return []


async def get_blood_request_by_id(
        db: AsyncSession,
        request_id: int
) -> Optional[BloodRequest]:
    """Fetches a single request by its primary key."""
    result = await db.execute(select(BloodRequest).where(BloodRequest.id == request_id))
    return result.scalar_one_or_none()


# -------------------------------------------------------------------------
# UPDATE: STATUS & LIFECYCLE
# -------------------------------------------------------------------------

async def update_request_status(
        db: AsyncSession,
        request_id: int,
        new_status: str
) -> Optional[BloodRequest]:
    """
    Updates the status of a blood request.
    Crucial for Modular Service logic (e.g., fulfilling, expiring, or cancelling).
    """
    try:
        stmt = (
            update(BloodRequest)
            .where(BloodRequest.id == request_id)
            .values(status=new_status)
            .returning(BloodRequest)
        )
        result = await db.execute(stmt)
        updated_obj = result.scalar_one_or_none()

        if updated_obj:
            logger.info(f"CRUD: Request {request_id} updated to {new_status}")

        return updated_obj
    except Exception as e:
        logger.error(f"CRUD Error (update_status): {e}")
        raise e