import os
import sys

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

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Setup
    db = database.SessionLocal()

    yield db

    # Cleanup - truncate all tables
    try:
        db.execute(text('''
            TRUNCATE TABLE users CASCADE;
        '''))
        db.commit()
    finally:
        db.close()

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:latest") as postgres:
        yield postgres

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
    yield session
    session.close()
