from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.schema.models import Base
from app.settings import get_settings
import logging
import time
from sqlalchemy.exc import OperationalError

_engine = None
_SessionLocal = None

def get_engine():
    """Get or create SQLAlchemy engine based on current settings"""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.get_database_url()
        if db_url:
            # Add retry logic for connection
            retry_count = 0
            max_retries = 3
            retry_delay = 2  # seconds

            while retry_count < max_retries:
                try:
                    _engine = create_engine(
                        db_url,
                        pool_pre_ping=True,  # Verify connections before using them
                        pool_recycle=300,    # Recycle connections every 5 minutes
                        # Increase connection timeout
                        connect_args={"connect_timeout": 30}
                    )
                    # Test connection
                    _engine.connect().close()
                    break
                except OperationalError as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logging.error(
                            f"Failed to connect to database after {max_retries} attempts: {e}")
                        raise
                    logging.warning(
                        f"Database connection failed (attempt {retry_count}/{max_retries}), retrying in {retry_delay}s: {e}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
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