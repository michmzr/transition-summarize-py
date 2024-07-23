import logging
import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    disable_cache: bool = False
    logging_level: int = logging.DEBUG
    openai_api_key: str

    # list of proxy servers, comma separated
    proxy_servers: str

    # paths
    base_dir: str = os.path.dirname(os.path.abspath(__file__))
    data_dir: str = os.path.join(base_dir, '/data/downloads')


@lru_cache
def get_settings():
    return Settings()
