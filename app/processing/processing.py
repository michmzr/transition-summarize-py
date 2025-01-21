from fastapi import Request
from app.schema.pydantic_models import CompletedProcess, User
from app.schema.models import ProcessArtifactDB, UserProcessDB, RequestType, RequestStatus
import logging
from app.database import SessionLocal
import uuid


def register_new_process(user: User, request_type: RequestType, request: Request, request_data: dict):
    logging.info(f"Registering new process for user {user.id} with request data {request}")

    db = SessionLocal()
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


def update_process_status(process_id: str, completed_process: CompletedProcess):
    logging.info(f"Updating process {process_id} status to {completed_process.status}")

    db = SessionLocal()
    try:
        process_uuid = uuid.UUID(process_id)
        
        request = db.query(UserProcessDB).filter(UserProcessDB.id == process_uuid).first()
        if not request:
            raise ValueError(f"Process {process_id} not found")
        
        request.status = completed_process.status

        if completed_process.result:
            result = ProcessArtifactDB(
                request_id=request.id,
                result=completed_process.result,
                result_format=completed_process.result_format,
                lang=completed_process.lang,
                user_id=completed_process.user_id,
            )

            if completed_process.source_file:
                request.source_file = completed_process.source_file
                request.source_file_size = completed_process.source_file_size
                request.source_file_type = completed_process.source_file_type
        
            db.add(result)
        db.commit()
        db.refresh(request)
    finally:
        db.close()