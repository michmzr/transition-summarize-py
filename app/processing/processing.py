from fastapi import Request
from app.schema.pydantic_models import CompletedProcess, User
from app.schema.models import ProcessArtifactDB, ProcessArtifactFormat, ProcessArtifactType, UserProcessDB, RequestType, RequestStatus, UserProcessSourceType
import logging
from uuid import UUID
from sqlalchemy.orm import Session
from app.database import get_session_maker
from app.transcribe.transcription import LANG_CODE


def register_new_process(user: User, request_type: RequestType, request: Request, request_data: dict) -> UUID:
    logging.info(f"Registering new process for user {user.id} with request data {request}")

    db = get_session_maker()()
    try:
        source_type = None
        match(request_type):
            case RequestType.AUDIO:
                source_type = UserProcessSourceType.FILE
            case RequestType.TEXT:
                source_type = UserProcessSourceType.URL
            case RequestType.YOUTUBE:
                source_type = UserProcessSourceType.URL
            case _:
                raise ValueError(f"Invalid request type: {request_type}")

        new_process = UserProcessDB(
            user_id=user.id,
            type=request_type,
            status=RequestStatus.PENDING,
            source_metadata=request_data,
            source_type=source_type
        )
        # todo add request.url to source_metadata

        db.add(new_process)
        db.commit()
        db.refresh(new_process)

        return new_process.id
    finally:
        db.close()


def get_db_session():
    SessionLocal = get_session_maker()
    return SessionLocal()


def update_process_status(process_id: UUID | str, completed_process: CompletedProcess) -> None:
    """
    Update process status and create artifact if result exists
    
    Args:
        process_id: UUID object or string representation of UUID
        completed_process: CompletedProcess object containing status and result info
    """
    # Convert string to UUID if needed
    if isinstance(process_id, str):
        try:
            process_uuid = UUID(process_id)
        except ValueError:
            raise ValueError(f"Invalid UUID format: {process_id}")
    else:
        process_uuid = process_id
    
    db = get_session_maker()()
    try:
        process = db.query(UserProcessDB).filter(UserProcessDB.id == process_uuid).first()
        if not process:
            raise ValueError(f"Process {process_id} not found")

        # Update process status
        process.status = completed_process.status
        
        # Create new artifact if result exists
        if completed_process.result is not None:
            artifact = ProcessArtifactDB(
                request_id=process_uuid,
                type=completed_process.type,
                result=completed_process.result,
                result_format=completed_process.result_format,
                lang=completed_process.lang,
                owner_id=completed_process.user_id,
                source_file=completed_process.source_file,
                source_file_size=completed_process.source_file_size,
                source_file_type=completed_process.source_file_type,
            )
            db.add(artifact)
        
        db.commit()
    finally:
        db.close()

def complete_process(
        process_id: UUID ) -> None:
    logging.info(f"Completing process {process_id}....")

    db = get_session_maker()()
    try:
        process = db.query(UserProcessDB).filter(UserProcessDB.id == process_id).first()
        if not process:
            raise ValueError(f"Process #{process_id} not found")

        # Update process status
        process.status = RequestStatus.COMPLETED
        
        db.commit()
    finally:
        db.close()

def process_failed(
        process_id: UUID, error:str | Exception ) -> None:
    logging.info(f"Process {process_id} failed with error: '{error}'")

    db = get_session_maker()()
    try:
        process = db.query(UserProcessDB) \
            .filter(UserProcessDB.id == process_id) \
            .first()
        if not process:
            raise ValueError(f"Process #{process_id} not found")

        process.status = RequestStatus.FAILED

        db.commit()
    finally:
        db.close()

def register_process_artifact(
        user: User, process_id: UUID, type: ProcessArtifactType, 
        result: str, result_format: ProcessArtifactFormat, lang: LANG_CODE):

    update_process_status(process_id, CompletedProcess(
        user_id=user.id,
        status=RequestStatus.COMPLETED,
        result=result,
        result_format=result_format,
        lang=lang,
        type=type))