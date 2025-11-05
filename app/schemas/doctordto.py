from pydantic import BaseModel

class DoctorDto(BaseModel):
    id: str
    name: str
    is_online: bool

    class Config:
        orm_mode = True

class RequestResponse(BaseModel):
    success: bool
    message: str
    request_id: str | None = None
