import logging
import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    disable_cache: bool = False
    logging_level: int = logging.DEBUG
    openai_api_key: str
    use_proxy: bool = True

    # list of proxy servers, comma separated
    proxy_servers: str

    # paths
    base_dir: str = os.path.dirname(os.path.abspath(__file__))
    data_dir: str = os.path.join(base_dir, '/data/downloads')

    # Database settings
    database_username: str
    database_password: str
    database_name: str
    database_url: str = f"postgresql://{{database_username}}:{{database_password}}@localhost:5432/{{database_name}}"

    # JWT settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Environment
    is_local: bool = False


@lru_cache
def get_settings():
    return Settings()
