from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import User, ServiceListing
from ..schemas.search import SearchItem

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


@router.get("/", response_model=List[SearchItem])
def global_search(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """
    Search across multiple modules (Healthcare, Transport, Blood)
    """
    try:
        search_pattern = f"%{q}%"

        # 1. Search Users (Doctors/Nurses/Donors)
        users = db.query(User).filter(User.full_name.ilike(search_pattern)).all()

        # 2. Search Services (Taxis/Bikes)
        services = db.query(ServiceListing).filter(ServiceListing.service_name.ilike(search_pattern)).all()

        combined_results = []

        # Map Users to SearchItem (6 parameters)
        for u in users:
            combined_results.append(SearchItem(
                id=str(u.id),
                title=u.full_name,
                subtitle=u.role.capitalize(),
                type=u.role.lower(),  # Logical constant for Android icons
                imageUrl=u.profile_image,
                category=u.role  # Display label
            ))

        # Map Services to SearchItem (6 parameters)
        for s in services:
            combined_results.append(SearchItem(
                id=str(s.id),
                title=s.service_name,
                subtitle=s.category.upper(),
                type=s.category.lower(),  # Logical constant for Android icons
                imageUrl=s.icon_url,
                category=s.category  # Display label
            ))

        return combined_results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))