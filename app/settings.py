import logging
import os
from functools import lru_cache

from langsmith.wrappers import wrap_openai
from openai import OpenAI, AsyncOpenAI
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
    openai_api_key: str = Field(alias="OPENAI_API_KEY")

    # Cleanup settings
    cleanup_downloads_enabled: bool = Field(
        default=True, alias="CLEANUP_DOWNLOADS_ENABLED")
    cleanup_downloads_age_days: int = Field(
        default=1, alias="CLEANUP_DOWNLOADS_AGE_DAYS")
    cleanup_downloads_time: str = Field(
        default="0 1 * * *", alias="CLEANUP_DOWNLOADS_TIME")  # Default: 1 AM daily

    # LangChain settings
    langchain_tracing_v2: bool = Field(default=False, json_schema_extra={"env": "LANGCHAIN_TRACING_V2"})
    langchain_endpoint: str = Field(default="", json_schema_extra={"env": "LANGCHAIN_ENDPOINT"})
    langchain_api_key: str = Field(default="", json_schema_extra={"env": "LANGCHAIN_API_KEY"})
    langchain_project: str = Field(default="", json_schema_extra={"env": "LANGCHAIN_PROJECT"})

    # Proxy settings
    use_proxy: bool = Field(default=False, json_schema_extra={"env": "USE_PROXY"})
    proxy_servers: str = Field(default="", json_schema_extra={"env": "PROXY_SERVERS"})

    # Paths
    base_dir: str = os.path.dirname(os.path.abspath(__file__))
    data_dir: str = os.path.join(base_dir, '/data/downloads')

    # Database settings - make optional during testing
    database_url: str | None = Field(
        default=None,
        alias="POSTGRES_URL",
        description="Database URL - can be None during testing when using testcontainers"
    )

    # JWT settings
    secret_key: str = Field(alias="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Environment
    is_local: bool = Field(default=False, alias="IS_LOCAL")
    testing: bool = Field(default=False, json_schema_extra={"env": "TESTING"})
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Security settings
    allowed_origins: str = Field(
        default="https://summarizer.cybershu.eu",
        alias="ALLOWED_ORIGINS"
    )
    allowed_hosts: str = Field(
        default="summarizer.cybershu.eu",
        alias="ALLOWED_HOSTS"
    )
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(
        default=60, alias="RATE_LIMIT_PERIOD")  # in seconds
    enable_rate_limiting: bool = Field(
        default=True, alias="ENABLE_RATE_LIMITING")
    enable_https_redirect: bool = Field(
        default=True, alias="ENABLE_HTTPS_REDIRECT")
    enable_security_headers: bool = Field(
        default=True, alias="ENABLE_SECURITY_HEADERS")
    enable_cors: bool = Field(default=True, alias="ENABLE_CORS")

    @property
    def is_production(self) -> bool:
        """Helper method to check if we're in production mode"""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Helper method to check if we're in development mode"""
        return self.environment == "development"

    @property
    def security_config(self) -> dict:
        """Get security configuration based on environment"""
        if self.is_production:
            return {
                "allowed_origins": self.allowed_origins.split(","),
                "allowed_hosts": self.allowed_hosts.split(","),
                "enable_rate_limiting": True,
                "enable_https_redirect": True,
                "enable_security_headers": True,
                "enable_cors": True
            }
        return {
            "allowed_origins": ["*"],
            "allowed_hosts": ["*"],
            "enable_rate_limiting": False,
            "enable_https_redirect": False,
            "enable_security_headers": True,
            "enable_cors": False
        }

    # Registration
    enable_registration: bool = Field(default=True, alias="ENABLE_REGISTRATION")

    @property
    def is_testing(self) -> bool:
        """Helper method to check if we're in testing mode"""
        return self.testing or os.getenv("TESTING") == "true"

    def get_database_url(self) -> str:
        """
        Get the database URL, handling the case where it might be None during testing
        """
        logging.info(f"Database URL present: {self.database_url is not None}, testing: {self.is_testing}")
        if self.is_testing and self.database_url is None:
            # Return a dummy URL during testing - will be overridden by testcontainers
            return "postgresql://postgres:postgres@localhost:5432/postgres"
        if self.database_url is None:
            raise ValueError("Database URL is required outside of testing context")
        return self.database_url


@lru_cache()
def get_settings():
    return Settings()


# AI Clients - with safer initialization
def get_openai_client():
    settings = get_settings()
    return wrap_openai(AsyncOpenAI(api_key=settings.openai_api_key))


# Initialize the OpenAI client lazily
client_openai = get_openai_client()
