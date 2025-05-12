from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.schema.models import Base
from app.settings import get_settings
import logging

_engine = None
_SessionLocal = None

def get_engine():
    """Get or create SQLAlchemy engine based on current settings"""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.get_database_url()
        if db_url:
            _engine = create_engine(db_url)
        else:
            # Handle case where URL is not available (e.g., misconfiguration)
            # Log an error or raise an exception as appropriate
            logging.error("Database URL is not configured.")
            # Optionally raise an exception:
            # raise ValueError("Database URL is not configured.")
            # Returning None might lead to issues downstream, like the TypeError observed
            pass  # Explicitly do nothing, _engine remains None

    return _engine

def get_session_maker():
    """Get or create session maker based on current engine"""
    global _SessionLocal
    if _SessionLocal is None:
        # Changed from engine to current_engine to avoid conflict
        current_engine = get_engine()
        if current_engine is not None:
            _SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=current_engine)
    return _SessionLocal

# Don't create tables automatically in test environment
def init_db():
    """Initialize database tables if not in test environment"""
    settings = get_settings()
    if not settings.is_testing:
        current_engine = get_engine()  # Changed from engine to current_engine
        if current_engine is not None:
            Base.metadata.create_all(bind=current_engine)

# Dependency
def get_db():
    # Use the getter to ensure SessionLocal is initialized
    SessionMaker = get_session_maker()
    if SessionMaker is None:
        # This might happen if the engine couldn't be created (e.g. in tests before fixture)
        # Or if DATABASE_URL is not set and not settings.is_testing
        # Depending on desired behavior, could raise an error or handle differently
        raise RuntimeError(
            "SessionLocal not initialized. Database engine might not be available.")
    db = SessionMaker()
    try:
        yield db
    finally:
        db.close()