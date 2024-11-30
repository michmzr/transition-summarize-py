import logging
import os
from functools import lru_cache

from langsmith.wrappers import wrap_openai
from openai import OpenAI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow"  # Allow extra fields not defined in the Settings class
    )

    # Basic settings
    disable_cache: bool = False
    logging_level: int = logging.DEBUG
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    use_proxy: bool = True

    # LangChain settings
    langchain_tracing_v2: bool = Field(default=False, env="LANGCHAIN_TRACING_V2")
    langchain_endpoint: str = Field(default="", env="LANGCHAIN_ENDPOINT")
    langchain_api_key: str = Field(default="", env="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="", env="LANGCHAIN_PROJECT")

    # Proxy settings
    proxy_servers: str = Field(default="", env="PROXY_SERVERS")

    # Paths
    base_dir: str = os.path.dirname(os.path.abspath(__file__))
    data_dir: str = os.path.join(base_dir, '/data/downloads')

    # Database settings
    database_username: str = Field(default="postgres", env="POSTGRES_USER", alias="DATABASE_USERNAME")
    database_password: str = Field(default="postgres", env="POSTGRES_PASSWORD", alias="DATABASE_PASSWORD")
    database_name: str = Field(default="test_db", env="POSTGRES_NAME", alias="DATABASE_NAME")
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/test_db",
        env="POSTGRES_URL",
        alias="DATABASE_URL"
    )
    database_host: str = Field(default="localhost", env="POSTGRES_HOST", alias="DATABASE_HOST")
    database_port: int = Field(default=5432, env="POSTGRES_PORT", alias="DATABASE_PORT")

    # JWT settings
    secret_key: str = Field(env="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Environment
    is_local: bool = Field(default=False, env="IS_LOCAL")

    # Registration
    enable_registration: bool = Field(default=True, env="ENABLE_REGISTRATION")


@lru_cache()
def get_settings():
    return Settings()

# AI Clients
client_openai = wrap_openai(OpenAI(api_key=get_settings().openai_api_key))
