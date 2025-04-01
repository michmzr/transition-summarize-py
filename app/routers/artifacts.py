from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.database import get_session_maker
from app.schema.models import ProcessArtifactDB, ProcessArtifactType
from app.schema.pydantic_models import User
from app.auth import get_current_user
from app.processing.processing import get_transcription_chunk
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(
    prefix="/artifacts",
    tags=["artifacts"],
    responses={404: {"description": "Not found"}},
)


class ArtifactResponse(BaseModel):
    id: UUID
    request_id: UUID
    type: str
    result_format: str
    lang: str
    created_at: datetime
    updated_at: datetime
    source_file: Optional[str] = None
    source_file_size: Optional[int] = None
    source_file_type: Optional[str] = None

    # For list views, we'll include a preview of the result
    result_preview: Optional[str] = None

    class Config:
        orm_mode = True


@router.get("/", response_model=List[ArtifactResponse])
async def list_artifacts(
    search: Optional[str] = None,
    artifact_type: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """
    List all process artifacts with optional filtering.
    """
    db = get_session_maker()()
    try:
        query = db.query(ProcessArtifactDB).filter(
            ProcessArtifactDB.owner_id == current_user.id
        )

        # Filter by type if provided
        if artifact_type:
            try:
                artifact_type_enum = ProcessArtifactType(artifact_type.lower())
                query = query.filter(
                    ProcessArtifactDB.type == artifact_type_enum)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid artifact type: {artifact_type}")

        # Filter by search term if provided
        if search:
            query = query.filter(ProcessArtifactDB.result.ilike(f"%{search}%"))

        # Apply pagination
        total = query.count()
        query = query.order_by(ProcessArtifactDB.created_at.desc())
        artifacts = query.offset(offset).limit(limit).all()

        # Create response with result preview
        result = []
        for artifact in artifacts:
            artifact_dict = {
                "id": artifact.id,
                "request_id": artifact.request_id,
                "type": artifact.type.value,
                "result_format": artifact.result_format.value,
                "lang": artifact.lang,
                "created_at": artifact.created_at,
                "updated_at": artifact.updated_at,
                "source_file": artifact.source_file,
                "source_file_size": artifact.source_file_size,
                "source_file_type": artifact.source_file_type,
                "result_preview": artifact.result[:200] + "..." if artifact.result and len(artifact.result) > 200 else artifact.result
            }
            result.append(artifact_dict)

        return result
    finally:
        db.close()


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific artifact by ID.
    """
    db = get_session_maker()()
    try:
        artifact = db.query(ProcessArtifactDB).filter(
            ProcessArtifactDB.id == artifact_id,
            ProcessArtifactDB.owner_id == current_user.id
        ).first()

        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")

        return {
            "id": artifact.id,
            "request_id": artifact.request_id,
            "type": artifact.type.value,
            "result_format": artifact.result_format.value,
            "lang": artifact.lang,
            "created_at": artifact.created_at,
            "updated_at": artifact.updated_at,
            "source_file": artifact.source_file,
            "source_file_size": artifact.source_file_size,
            "source_file_type": artifact.source_file_type,
            "result_preview": artifact.result
        }
    finally:
        db.close()


@router.get("/{artifact_id}/content")
async def get_artifact_content(
    artifact_id: UUID,
    start: int = Query(0, ge=0),
    chunk_size: int = Query(10000, ge=1, le=50000),
    current_user: User = Depends(get_current_user)
):
    """
    Get the content of an artifact in chunks to handle large texts efficiently.
    """
    db = get_session_maker()()
    try:
        # First verify the user has access to this artifact
        artifact = db.query(ProcessArtifactDB).filter(
            ProcessArtifactDB.id == artifact_id,
            ProcessArtifactDB.owner_id == current_user.id
        ).first()

        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")

        # Get the content chunk
        chunk_text, total_size, has_more = get_transcription_chunk(
            artifact_id=artifact_id,
            start_pos=start,
            chunk_size=chunk_size
        )

        return {
            "content": chunk_text,
            "total_size": total_size,
            "start": start,
            "end": start + len(chunk_text),
            "has_more": has_more
        }
    finally:
        db.close()
