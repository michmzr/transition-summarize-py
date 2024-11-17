from functools import lru_cache
from app.settings import get_settings as _get_settings

@lru_cache()
def get_settings():
    return _get_settings()

def get_downloads_path():
    return get_settings().data_dir 