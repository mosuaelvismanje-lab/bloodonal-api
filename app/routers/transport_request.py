# app/routers/transport_request.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.schemas.transport_request import TransportRequestCreate, TransportRequest
from app.crud.transport_request import create_transport_request, get_transport_requests
from app.dependencies import get_db

router = APIRouter(prefix="/transport-requests", tags=["TransportRequests"])


@router.post("/", response_model=TransportRequest)
def create_transport(req: TransportRequestCreate, db: Session = Depends(get_db)):
    try:
        return create_transport_request(db, req)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not create transport request") from e


@router.get("/", response_model=List[TransportRequest])
def list_transport_requests(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        return get_transport_requests(db, skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not fetch transport requests") from e
