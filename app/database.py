from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.schema.models import Base
from app.settings import get_settings

_engine = None
_SessionLocal = None

def get_engine():
    """Get or create SQLAlchemy engine based on current settings"""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.get_database_url())
    return _engine

def get_session_maker():
    """Get or create session maker based on current engine"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal

# For backwards compatibility
engine = get_engine()
SessionLocal = get_session_maker()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()