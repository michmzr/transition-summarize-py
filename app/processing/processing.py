from fastapi import Request
from app.schema.pydantic_models import CompletedProcess, User
from app.schema.models import ProcessArtifactDB, ProcessArtifactFormat, ProcessArtifactType, UserProcessDB, RequestType, RequestStatus, UserProcessSourceType
import logging
from uuid import UUID
from app.database import get_session_maker
from app.transcribe.transcription import LANG_CODE
import hashlib
from sqlalchemy import text


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
            # Calculate hash for the result (first 8KB to avoid performance issues with very large texts)
            result_hash = None
            if completed_process.result:
                result_hash = hashlib.sha256(
                    completed_process.result[:8192].encode('utf-8')).hexdigest()

            artifact = ProcessArtifactDB(
                request_id=process_uuid,
                type=completed_process.type,
                result=completed_process.result,
                result_format=completed_process.result_format,
                result_hash=result_hash,
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


def search_created_artifacts(search_term: str, user_id: UUID = None, limit: int = 10, offset: int = 0):
    """
    Search for artifacts containing the given search term.
    Uses the optimized substring index for efficient searching.
    
    Args:
        search_term: Text to search for in artifacts like transcription, summary, etc.
        user_id: Optional user ID to filter results by owner
        limit: Maximum number of results to return
        offset: Number of results to skip (for pagination)
        
    Returns:
        List of matching ProcessArtifactDB objects
    """
    db = get_session_maker()()
    try:
        query = db.query(ProcessArtifactDB)

        # If search term is provided, use the optimized substring index
        if search_term:
            # Use the substring index which only indexes the first 1000 characters
            # This avoids the index size limit issue
            query = query.filter(
                ProcessArtifactDB.result.ilike(f'%{search_term}%')
            )

        # Filter by user if provided
        if user_id:
            query = query.filter(ProcessArtifactDB.owner_id == user_id)

        # Apply pagination
        query = query.order_by(ProcessArtifactDB.created_at.desc())
        query = query.limit(limit).offset(offset)

        return query.all()
    finally:
        db.close()


def get_transcription_chunk(artifact_id: UUID, start_pos: int = 0, chunk_size: int = 10000):
    """
    Retrieve a chunk of a large transcription to avoid loading the entire text into memory.
    
    Args:
        artifact_id: ID of the ProcessArtifactDB object
        start_pos: Starting position in the text (character offset)
        chunk_size: Maximum number of characters to retrieve
        
    Returns:
        Tuple containing (chunk_text, total_size, has_more)
    """
    db = get_session_maker()()
    try:
        # Use SQLAlchemy's text function to create a raw SQL query that efficiently
        # extracts just the substring we need without loading the entire text

        # First get the total size of the text
        size_query = text("""
            SELECT pg_column_size(result) 
            FROM process_artifacts 
            WHERE id = :artifact_id
        """)

        total_size = db.execute(
            size_query, {"artifact_id": artifact_id}).scalar() or 0

        # Then get just the chunk we need
        chunk_query = text("""
            SELECT substring(result from :start_pos for :chunk_size)
            FROM process_artifacts
            WHERE id = :artifact_id
        """)

        chunk_text = db.execute(
            chunk_query,
            {"artifact_id": artifact_id, "start_pos": start_pos +
                1, "chunk_size": chunk_size}
        ).scalar() or ""

        # Check if there's more text after this chunk
        has_more = (start_pos + len(chunk_text)) < total_size

        return chunk_text, total_size, has_more
    finally:
        db.close()
