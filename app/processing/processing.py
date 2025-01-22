from fastapi import Request
from app.schema.pydantic_models import CompletedProcess, User
from app.schema.models import ProcessArtifactDB, UserProcessDB, RequestType, RequestStatus
import logging
from uuid import UUID
from sqlalchemy.orm import Session
from app.database import get_session_maker


def register_new_process(user: User, request_type: RequestType, request: Request, request_data: dict):
    logging.info(f"Registering new process for user {user.id} with request data {request}")

    db = get_session_maker()()
    try:
        new_process = UserProcessDB(
            user_id=user.id,
            type=request_type,
            status=RequestStatus.PENDING,
            request_data=request_data
        )

        db.add(new_process)
        db.commit()
        db.refresh(new_process)

        return new_process
    finally:
        db.close()


def get_db_session():
    SessionLocal = get_session_maker()
    return SessionLocal()


def update_process_status(process_id: str, completed_process: CompletedProcess) -> None:
    try:
        process_uuid = UUID(process_id)
    except ValueError:
        raise ValueError(f"Invalid UUID format: {process_id}")
    
    db = get_db_session()
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
                source_file_type=completed_process.source_file_type
            )
            db.add(artifact)
        
        db.commit()
    finally:
        db.close()