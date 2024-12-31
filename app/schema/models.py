import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Integer, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

class RequestType(enum.Enum):
    AUDIO = "audio"
    TEXT = "text"
    FILE = "file"

class RequestStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessingType(enum.Enum):
    TRANSCRIPTION = "transcription"
    SUMMARY = "summary"

class ProcessingResultFormat(enum.Enum):
    TEXT = "text"
    SRT = "srt"
    JSON = "json"

class UserDB(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

    __table_args__ = {'extend_existing': True}

class UserRequestDB(Base):
    __tablename__ = "urequests"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    type = Column(Enum(RequestType), nullable=False)
    status = Column(Enum(RequestStatus), nullable=False)

    request_data = Column(JSONB)  # Use JSONB for better performance and flexibility

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = {'extend_existing': True}

class ProcessingResultDB(Base):
    __tablename__ = "processing_results"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)

    request_id = Column(UUID(as_uuid=True), ForeignKey("urequests.id"))

    type = Column(Enum(ProcessingType), nullable=False)

    result = Column(Text)  # Changed from String to Text to handle large text data
    result_format = Column(Enum(ProcessingResultFormat), nullable=False)
    
    lang = Column(String)  # Consider using an ENUM if the languages are fixed

    source_file = Column(String, nullable=True)
    source_file_size = Column(Integer, nullable=True)
    source_file_type = Column(String, nullable=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = {'extend_existing': True}
