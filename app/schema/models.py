import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Integer, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TEXT
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

class UserDB(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

    __table_args__ = {'extend_existing': True}

class RequestType(enum.Enum):
    AUDIO = "audio"
    TEXT = "text"
    FILE = "file"
    YOUTUBE = "youtube"

class RequestStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessArtifactType(enum.Enum):
    TRANSCRIPTION = "transcription"
    SUMMARY = "summary"

class ProcessArtifactFormat(enum.Enum):
    TEXT = "text"
    SRT = "srt"
    JSON = "json"

class UserProcessSourceType(enum.Enum):
    FILE = "file"
    URL = "url"

class UserProcessDB(Base):
    __tablename__ = "uprocess"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)

    type = Column(Enum(RequestType), nullable=False)
    status = Column(Enum(RequestStatus), nullable=False)

    request_data = Column(JSONB)

    source_metadata = Column(JSONB, nullable=False)
    source_type = Column(Enum(UserProcessSourceType), nullable=False)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = {'extend_existing': True}

class ProcessArtifactDB(Base):
    __tablename__ = "process_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)

    request_id = Column(UUID(as_uuid=True), ForeignKey("uprocess.id"))

    type = Column(Enum(ProcessArtifactType), nullable=False)

    result = Column(TEXT)
    result_format = Column(Enum(ProcessArtifactFormat), nullable=False)
    result_hash = Column(String(64), nullable=True, index=True)
    
    lang = Column(String)  # Consider using an ENUM if the languages are fixed

    source_file = Column(String, nullable=True)
    source_file_size = Column(Integer, nullable=True)
    source_file_type = Column(String, nullable=True)

    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = {'extend_existing': True}
