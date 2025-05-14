from app.schema.models import Base  # Import Base for table creation
import os
import sys
import time
import logging
import socket
import subprocess
from typing import Callable

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


def wait_for_ready(check_func: Callable[[], bool], timeout: int = 180, interval: int = 2):
    """Wait for a condition to be true with exponential backoff"""
    start_time = time.time()
    current_interval = interval
    max_interval = 10  # Maximum wait between attempts

    while time.time() - start_time < timeout:
        try:
            if check_func():
                return True
        except Exception as e:
            testcontainers_logger.warning(f"Failed readiness check: {e}")

        # Log waiting message every few seconds
        testcontainers_logger.info(
            f"Waiting for readiness check (elapsed: {int(time.time() - start_time)}s)...")
        time.sleep(current_interval)

        # Exponential backoff with a maximum
        current_interval = min(current_interval * 1.5, max_interval)

    return False

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

    # Increase startup timeout (default seems to be too short)
    postgres_container.start_timeout = 300  # 5 minutes

    # Use random available port
    postgres_container.with_bind_ports(5432, 0)

    try:
        testcontainers_logger.info("Starting PostgreSQL container...")
        postgres_container.start()

        # Print container logs immediately after start
        print("\n=== PostgreSQL Container Logs ===")
        print(postgres_container._container.logs().decode())
        print("=================================\n")

        # Get the actual port and create database URL
        actual_port = postgres_container.get_exposed_port(5432)
        db_url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:{actual_port}/{POSTGRES_DB}"

        # Wait for PostgreSQL to be ready
        def check_postgres_ready():
            # Try connecting directly to the database
            try:
                # Create a test connection to verify DB is ready
                test_engine = create_engine(db_url)
                with test_engine.connect() as connection:
                    result = connection.execute(text("SELECT 1"))
                    return result.scalar() == 1
            except Exception as e:
                testcontainers_logger.warning(f"Database not ready yet: {e}")
                return False

        testcontainers_logger.info("Waiting for PostgreSQL to be ready...")
        if not wait_for_ready(check_postgres_ready, timeout=240):
            # If we reach here, the wait timed out
            logs = postgres_container._container.logs().decode()
            testcontainers_logger.error(
                f"PostgreSQL container failed to become ready. Logs:\n{logs}")
            raise TimeoutError(
                "PostgreSQL container failed to become ready in the allocated time")

        testcontainers_logger.info("PostgreSQL is ready!")

        # Update settings
        override_settings.database_url = db_url
        os.environ["POSTGRES_URL"] = db_url

        # Create tables in the test database
        engine = create_engine(db_url)
        Base.metadata.create_all(bind=engine)
        engine.dispose()  # Close the engine after creating tables

        # Monitor container logs during test execution
        def print_logs():
            while True:
                print(postgres_container._container.logs().decode())
                time.sleep(5)

        import threading
        log_thread = threading.Thread(target=print_logs, daemon=True)
        log_thread.start()

        yield postgres_container
    except Exception as e:
        testcontainers_logger.error(f"Failed to start PostgreSQL container: {e}")
        print("\n=== Error Logs ===")
        print(postgres_container._container.logs().decode())
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

    def override_get_session_maker():
        return TestingSessionLocal

    from app import database
    monkeypatch.setattr(database, "get_session_maker",
                        override_get_session_maker)

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
