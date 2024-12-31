import uuid

from pydantic import BaseModel, EmailStr

from app.schema.models import ProcessingResultFormat, RequestStatus
from app.transcribe.transcription import LANG_CODE


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: uuid.UUID
    is_active: bool

    class Config:
        from_attributes = True


class UserInDB(User):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class CompletedProcess(BaseModel):
    status: RequestStatus

    result: str
    result_format: ProcessingResultFormat

    lang: LANG_CODE

    user_id: uuid.UUID

    # optional fields
    source_file: str | None = None
    source_file_size: int | None = None
    source_file_type: str | None = None
    
