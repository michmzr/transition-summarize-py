import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase
import enum

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

class UserDB(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

    __table_args__ = {'extend_existing': True}

class RequestDB(Base):
    __tablename__ = "requests"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    type = Column(Enum(RequestType), nullable=False)
    status = Column(Enum(RequestStatus), nullable=False)

    request_data = Column(JSONB)  # Use JSONB for better performance and flexibility

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = {'extend_existing': True}

class ProcessingResultDB(Base):
    __tablename__ = "transcriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)

    type = Column(Enum(ProcessingType), nullable=False)

    result = Column(String)  # Consider using a more appropriate type if the result is large
    result_format = Column(Enum(ProcessingResultFormat), nullable=False)
    
    lang = Column(String)  # Consider using an ENUM if the languages are fixed
    response_format = Column(String)  # Consider using an ENUM if the formats are fixed

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    source_file = Column(String, nullable=True)
    source_file_size = Column(Integer, nullable=True)
    source_file_type = Column(String, nullable=True)

    __table_args__ = {'extend_existing': True}
