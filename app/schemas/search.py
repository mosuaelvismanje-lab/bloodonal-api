from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class SearchItem(BaseModel):
    id: str
    title: str
    subtitle: str
    type: str
    imageUrl: Optional[str] = None
    category: str

    class Config:
        from_attributes = True