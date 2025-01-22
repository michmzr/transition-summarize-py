from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.schema.models import Base
from app.settings import get_settings

def get_engine():
    """Get or create SQLAlchemy engine based on current settings"""
    settings = get_settings()
    return create_engine(settings.database_url)

def get_session_maker():
    """Get or create session maker based on current engine"""
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())

# Dependency
def get_db():
    session_maker = get_session_maker()
    db = session_maker()
    try:
        yield db
    finally:
        db.close()