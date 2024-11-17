import os
from functools import lru_cache
from app.settings import get_settings as _get_settings

@lru_cache()
def get_settings():
    return _get_settings()

def get_downloads_path():
    settings = get_settings()
    return settings.data_dir