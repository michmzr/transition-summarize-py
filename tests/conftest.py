import os
import sys
import logging

import pytest
from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

# Get the absolute path of the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from app import database
from app.settings import get_settings

# Configure logging at the top of conftest.py
logging.basicConfig(level=logging.INFO)
testcontainers_logger = logging.getLogger("testcontainers")
testcontainers_logger.setLevel(logging.DEBUG)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db(postgres_container, engine):
    from app.schema.models import Base

    Base.metadata.create_all(bind=engine)

    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database._engine = engine
    database._SessionLocal = testing_session_local
    database.engine = engine
    database.SessionLocal = testing_session_local

    db = testing_session_local()

    yield db

    try:
        print("Truncating test tables")
        db.execute(text('''
            TRUNCATE TABLE users, uprocess, process_artifacts CASCADE;
        '''))
        db.commit()
    finally:
        db.close()

@pytest.fixture(scope="session", autouse=True)
def override_settings():
    """Override settings before any database connections are made"""
    settings = get_settings()
    settings.testing = True
    settings.is_local = True
    settings.enable_registration = True
    settings.database_url = None  # Will be set by postgres_container fixture
    
    # Override environment variables for testing
    os.environ.update({
        "IS_LOCAL": "true",
        "ENABLE_REGISTRATION": "true",
        "LANGCHAIN_TRACING_V2": "false",
        "LANGCHAIN_ENDPOINT": "",
        "LANGCHAIN_PROJECT": "",
        "LANGCHAIN_API_KEY": "",
        "SECRET_KEY": "test_secret_key",
        "OPENAI_API_KEY": "test_openai_key",
    })
    
    return settings

def _clear_empty_postgres_env_vars() -> None:
    for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST", "POSTGRES_PORT"):
        if os.environ.get(key) == "":
            os.environ.pop(key, None)


def _print_postgres_logs(container: PostgresContainer) -> None:
    if not container._container:
        return
    stdout, stderr = container.get_logs()
    print("\n=== PostgreSQL Container Logs ===")
    print(stdout.decode())
    if stderr:
        print(stderr.decode())
    print("=================================\n")


@pytest.fixture(scope="session")
def postgres_container(override_settings):
    _clear_empty_postgres_env_vars()

    postgres_user = "postgres"
    postgres_password = "postgres"
    postgres_db = "postgres"

    container = PostgresContainer(
        "postgres:15-alpine",
        username=postgres_user,
        password=postgres_password,
        dbname=postgres_db,
    )

    try:
        testcontainers_logger.info("Starting PostgreSQL container...")
        container.start()
        _print_postgres_logs(container)

        db_url = container.get_connection_url()
        override_settings.database_url = db_url
        os.environ["POSTGRES_URL"] = db_url

        yield container
    except Exception as e:
        testcontainers_logger.error(f"Failed to start PostgreSQL container: {e}")
        print("\n=== Error Logs ===")
        _print_postgres_logs(container)
        raise
    finally:
        container.stop()

@pytest.fixture(scope="session")
def db_url(postgres_container):
    return postgres_container.get_connection_url()

@pytest.fixture(scope="session")
def engine(db_url):
    eng = create_engine(db_url)
    yield eng
    eng.dispose()

@pytest.fixture(scope="function")
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

# Override the database.SessionLocal to use test database
@pytest.fixture(autouse=True)
def override_db_session(monkeypatch, engine):
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(database, "_engine", engine)
    monkeypatch.setattr(database, "_SessionLocal", testing_session_local)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", testing_session_local)
    monkeypatch.setattr(database, "get_session_maker", lambda: testing_session_local)

@pytest.fixture(scope="function")
def test_db(postgres_container):
    """Get a test database session"""
    session_maker = get_session_maker()
    db = session_maker()
    
    yield db

    print("Cleaning up test database")
    
    # Cleanup after each test
    db.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()
