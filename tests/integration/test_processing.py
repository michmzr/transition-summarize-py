import uuid
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import alembic.config

# Import models and enums
from app.schema.models import (
    Base,
    RequestStatus,
    UserProcessDB as UserRequestDB,  # Alias for clarity in tests
    ProcessArtifactDB as ProcessingResultDB,  # Alias for clarity in tests
     RequestType,
    ProcessArtifactType,
    ProcessArtifactFormat,
    UserProcessSourceType,
)
from app.processing.processing import update_process_status, CompletedProcess

class TestProcessingIntegration:
    @pytest.fixture(scope="class")
    def postgres_container(self):
        with PostgresContainer("postgres:latest") as postgres:
            yield postgres

    @pytest.fixture(scope="class")
    def db_engine(self, postgres_container):
        connection_url = postgres_container.get_connection_url()
        engine = create_engine(connection_url)
        
        # Run migrations
        alembicArgs = [
            '--raiseerr',
            'upgrade', 'head',
        ]
        alembic.config.main(argv=alembicArgs)
        
        return engine

    @pytest.fixture
    def db_session(self, db_engine):
        Session = sessionmaker(bind=db_engine)
        session = Session()
        yield session
        session.close()

    @pytest.fixture
    def test_user_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def test_request(self, db_session, test_user_id):
        request = UserRequestDB(
            id=uuid.uuid4(),
            user_id=test_user_id,
            type=RequestStatus.PENDING,
            status=RequestStatus.PENDING,
            source_type="file",
            source_metadata={"filename": "test.mp3"}
        )
        db_session.add(request)
        db_session.commit()
        return request

    def test_given_pending_request_when_process_completes_successfully_then_status_and_result_are_updated(
        self, db_session, test_request, test_user_id
    ):
        # Given
        completed_process = CompletedProcess(
            status=RequestStatus.COMPLETED,
            result="Test transcription result",
            result_format=ProcessArtifactFormat.TEXT,
            lang="en",
            user_id=test_user_id,
            type=ProcessArtifactType.TRANSCRIPTION
        )

        # When
        update_process_status(str(test_request.id), completed_process)

        # Then
        updated_request = db_session.query(UserRequestDB).filter_by(id=test_request.id).first()
        assert updated_request.status == RequestStatus.COMPLETED

        result = db_session.query(ProcessingResultDB).filter_by(request_id=test_request.id).first()
        assert result is not None
        assert result.result == "Test transcription result"
        assert result.result_format == ProcessArtifactFormat.TEXT
        assert result.lang == "en"

    def test_given_pending_request_when_process_fails_then_status_is_updated_without_result(
        self, db_session, test_request
    ):
        # Given
        completed_process = CompletedProcess(
            status=RequestStatus.FAILED,
            result=None,
            result_format=None,
            lang=None,
            user_id=test_request.user_id,
            type=ProcessArtifactType.TRANSCRIPTION
        )

        # When
        update_process_status(str(test_request.id), completed_process)

        # Then
        updated_request = db_session.query(UserRequestDB).filter_by(id=test_request.id).first()
        assert updated_request.status == RequestStatus.FAILED

        result = db_session.query(ProcessingResultDB).filter_by(request_id=test_request.id).first()
        assert result is None

    def test_given_pending_request_when_process_completes_with_source_file_then_all_metadata_is_updated(
        self, db_session, test_request, test_user_id
    ):
        # Given
        completed_process = CompletedProcess(
            status=RequestStatus.COMPLETED,
            result="Test result",
            result_format=ProcessArtifactFormat.TEXT,
            lang="en",
            user_id=test_user_id,
            type=ProcessArtifactType.TRANSCRIPTION,
            source_file="processed.mp3",
            source_file_size=1024,
            source_file_type="audio/mp3"
        )

        # When
        update_process_status(str(test_request.id), completed_process)

        # Then
        updated_request = db_session.query(UserRequestDB).filter_by(id=test_request.id).first()
        assert updated_request.source_file == "processed.mp3"
        assert updated_request.source_file_size == 1024
        assert updated_request.source_file_type == "audio/mp3"

    def test_given_nonexistent_process_id_when_updating_status_then_raises_value_error(
        self, db_session
    ):
        # Given
        nonexistent_id = uuid.uuid4()
        completed_process = CompletedProcess(
            status=RequestStatus.COMPLETED,
            result="Test result",
            result_format=ProcessArtifactFormat.TEXT,
            lang="en",
            user_id=uuid.uuid4(),
            type=ProcessArtifactType.TRANSCRIPTION
        )

        # When/Then
        with pytest.raises(ValueError) as exc_info:
            update_process_status(str(nonexistent_id), completed_process)
        assert f"Process {nonexistent_id} not found" in str(exc_info.value)

    def test_given_invalid_uuid_format_when_updating_status_then_raises_value_error(
        self, db_session
    ):
        # Given
        invalid_id = "not-a-uuid"
        completed_process = CompletedProcess(
            status=RequestStatus.COMPLETED,
            result="Test result",
            result_format=ProcessArtifactFormat.TEXT,
            lang="en",
            user_id=uuid.uuid4(),
            type=ProcessArtifactType.TRANSCRIPTION
        )

        # When/Then
        with pytest.raises(ValueError) as exc_info:
            update_process_status(invalid_id, completed_process)

    def test_given_completed_request_when_updating_status_then_updates_existing_result(
        self, db_session, test_request, test_user_id
    ):
        # Given
        initial_process = CompletedProcess(
            status=RequestStatus.COMPLETED,
            result="Initial result",
            result_format=ProcessArtifactFormat.TEXT,
            lang="en",
            user_id=test_user_id,
            type=ProcessArtifactType.TRANSCRIPTION
        )
        update_process_status(str(test_request.id), initial_process)

        # When
        updated_process = CompletedProcess(
            status=RequestStatus.COMPLETED,
            result="Updated result",
            result_format=ProcessArtifactFormat.TEXT,
            lang="es",
            user_id=test_user_id,
            type=ProcessArtifactType.TRANSCRIPTION
        )
        update_process_status(str(test_request.id), updated_process)

        # Then
        results = db_session.query(ProcessingResultDB).filter_by(request_id=test_request.id).all()
        assert len(results) == 2
        assert any(r.result == "Updated result" and r.lang == "es" for r in results) 