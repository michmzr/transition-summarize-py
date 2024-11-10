import os
import sys

import pytest
from sqlalchemy import text

from app import database

# Get the absolute path of the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)


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
