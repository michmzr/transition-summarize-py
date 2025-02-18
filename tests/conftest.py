import os
import sys
import time

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
    
    # Force test settings
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
    postgres_container = PostgresContainer("postgres:latest")
    
    # Set default PostgreSQL credentials
    POSTGRES_USER = "postgres"
    POSTGRES_PASSWORD = "postgres"
    POSTGRES_DB = "postgres"
    
    # Configure container with credentials and create user
    postgres_container.with_env("POSTGRES_USER", POSTGRES_USER)
    postgres_container.with_env("POSTGRES_PASSWORD", POSTGRES_PASSWORD)
    postgres_container.with_env("POSTGRES_DB", POSTGRES_DB)
    postgres_container.with_env("POSTGRES_HOST_AUTH_METHOD", "trust")  # Changed from md5 to trust
    
    # Use random available port
    postgres_container.with_bind_ports(5432, 0)
    
    # Start the container
    postgres_container.start()
    
    # Get the actual port that was assigned
    actual_port = postgres_container.get_exposed_port(5432)
    
    # Construct database URL with proper credentials
    db_url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:{actual_port}/{POSTGRES_DB}"
    
    # Wait a bit longer for the container to fully initialize
    time.sleep(5)  # Increased from 2 to 5 seconds
    
    # Create postgres role and set up database
    engine = create_engine(db_url)
    with engine.connect() as conn:
        # Create postgres role if it doesn't exist
        conn.execute(text("""
            DO
            $do$
            BEGIN
               IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'postgres') THEN
                  CREATE ROLE postgres WITH SUPERUSER LOGIN PASSWORD 'postgres';
               END IF;
            END
            $do$;
        """))
        conn.commit()
        
        # Drop and recreate schema
        conn.execute(text("""
            DROP SCHEMA IF EXISTS public CASCADE;
            CREATE SCHEMA public;
            GRANT ALL ON SCHEMA public TO postgres;
            GRANT ALL ON SCHEMA public TO public;
        """))
        conn.commit()
    
    # Set the database URL in settings and environment
    override_settings.database_url = db_url
    
    # Set database-specific environment variables
    os.environ.update({
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": str(actual_port),
        "POSTGRES_USER": POSTGRES_USER,
        "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
        "POSTGRES_DB": POSTGRES_DB,
        "DATABASE_URL": db_url
    })

    # Get settings instance and update database URL
    settings = get_settings()
    settings.database_url = db_url
    
    # Run migrations
    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    
    yield postgres_container
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
