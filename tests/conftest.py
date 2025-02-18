import os
import sys
import time
import logging

import pytest
from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer
import alembic.config

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
def setup_test_db(postgres_container):
    # Setup
    db = database.get_session_maker()()

    yield db

    # Cleanup - truncate all tables
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

@pytest.fixture(scope="session")
def postgres_container(override_settings):
    postgres_container = PostgresContainer("postgres:15-alpine")
    
    # Set default PostgreSQL credentials
    POSTGRES_USER = "postgres"
    POSTGRES_PASSWORD = "postgres"
    POSTGRES_DB = "postgres"
    
    # Configure container with credentials
    postgres_container.with_env("POSTGRES_USER", POSTGRES_USER)
    postgres_container.with_env("POSTGRES_PASSWORD", POSTGRES_PASSWORD)
    postgres_container.with_env("POSTGRES_DB", POSTGRES_DB)
    postgres_container.with_env("POSTGRES_HOST_AUTH_METHOD", "trust")
    
    # Configure container startup
    postgres_container.with_env("PGDATA", "/var/lib/postgresql/data")
    postgres_container.with_env("POSTGRES_INITDB_ARGS", "--auth=trust")
    postgres_container.start_timeout = 180
    
    # Configure health check
    postgres_container.with_command([
        "postgres",
        "-c", "max_connections=100",
        "-c", "shared_buffers=256MB",
        "-c", "fsync=off",
        "-c", "synchronous_commit=off",
        "-c", "full_page_writes=off"
    ])
    
    # Use random available port
    postgres_container.with_bind_ports(5432, 0)
    
    try:
        testcontainers_logger.info("Starting PostgreSQL container...")
        postgres_container.start()
        
        # Get the actual port and create database URL
        actual_port = postgres_container.get_exposed_port(5432)
        db_url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:{actual_port}/{POSTGRES_DB}"
        
        # Update settings
        override_settings.database_url = db_url
        os.environ["POSTGRES_URL"] = db_url
        
        yield postgres_container
    except Exception as e:
        testcontainers_logger.error(f"Failed to start PostgreSQL container: {e}")
        raise
    finally:
        postgres_container.stop()

@pytest.fixture(scope="session")
def db_url(postgres_container):
    return postgres_container.get_connection_url()

@pytest.fixture(scope="session")
def engine(db_url):
    return create_engine(db_url)

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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    from app import database
    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)

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
