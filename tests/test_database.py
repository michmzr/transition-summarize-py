from app import database
from app.settings import get_settings


def test_get_engine_checks_pooled_connections_before_checkout(monkeypatch):
    created_engine = object()
    captured_kwargs = {}

    def fake_create_engine(database_url, **kwargs):
        captured_kwargs.update(kwargs)
        return created_engine

    settings = get_settings()
    original_testing = settings.testing
    original_database_url = settings.database_url

    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "create_engine", fake_create_engine)

    try:
        settings.testing = False
        settings.database_url = "postgresql://db/app"

        engine = database.get_engine()
    finally:
        settings.testing = original_testing
        settings.database_url = original_database_url
        database._engine = None

    assert engine is created_engine
    assert captured_kwargs["pool_pre_ping"] is True
    assert captured_kwargs["pool_recycle"] == 1800
