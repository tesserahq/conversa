import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, model_validator
from typing import Optional
from pydantic_settings import BaseSettings
from sqlalchemy.engine.url import make_url, URL

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/conversa"
DEFAULT_TEST_DATABASE_URL = (
    "postgresql://postgres:postgres@localhost:5432/conversa_test"
)

# Project root (parent of app/) - used so .env is found regardless of cwd
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Explicitly load .env into os.environ so it works in tests and subprocesses
load_dotenv(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    app_name: str = "conversa-api"
    vaulta_api_url: str = Field(
        default="http://localhost:8004", json_schema_extra={"env": "VAULTA_API_URL"}
    )
    otel_enabled: bool = Field(default=False, json_schema_extra={"env": "OTEL_ENABLED"})
    database_url: Optional[str] = None  # Will be set dynamically
    database_pool_size: int = Field(
        default=10, json_schema_extra={"env": "DATABASE_POOL_SIZE"}
    )
    database_max_overflow: int = Field(
        default=20, json_schema_extra={"env": "DATABASE_MAX_OVERFLOW"}
    )
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENV", "ENVIRONMENT"),
    )
    log_level: str = Field(default="INFO", json_schema_extra={"env": "LOG_LEVEL"})
    disable_auth: bool = Field(default=False, json_schema_extra={"env": "DISABLE_AUTH"})
    port: int = Field(default=8000, json_schema_extra={"env": "PORT"})
    identies_base_url: Optional[str] = Field(
        default=None,
        json_schema_extra={"env": "IDENTIES_HOST"},
    )
    rollbar_access_token: Optional[str] = Field(
        default=None, json_schema_extra={"env": "ROLLBAR_ACCESS_TOKEN"}
    )  # Optional field

    oidc_domain: str = "test.oidc.com"
    oidc_api_audience: str = "https://test-api"
    oidc_issuer: str = "https://test.oidc.com/"
    oidc_algorithms: str = "RS256"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_service_name: str = "conversa"
    fernet_key: Optional[str] = Field(
        default=None, json_schema_extra={"env": "FERNET_KEY"}
    )
    credential_master_key: Optional[str] = Field(
        default=None,
        json_schema_extra={"env": "CREDENTIAL_MASTER_KEY"},
    )
    fernet_salt: str = Field(
        default="default-salt", json_schema_extra={"env": "FERNET_SALT"}
    )

    redis_host: str = Field(
        default="localhost", json_schema_extra={"env": "REDIS_HOST"}
    )
    redis_port: int = Field(default=6379, json_schema_extra={"env": "REDIS_PORT"})
    redis_namespace: str = Field(
        default="llama_index", json_schema_extra={"env": "REDIS_NAMESPACE"}
    )
    service_account_client_id: str = Field(
        default="", json_schema_extra={"env": "SERVICE_ACCOUNT_CLIENT_ID"}
    )
    service_account_client_secret: str = Field(
        default="", json_schema_extra={"env": "SERVICE_ACCOUNT_CLIENT_SECRET"}
    )
    quore_enabled: bool = Field(
        default=False, json_schema_extra={"env": "QUORE_ENABLED"}
    )
    quore_api_url: str = Field(
        default="https://quore-api.meetconversa.com",
        json_schema_extra={"env": "QUORE_API_URL"},
    )
    nats_enabled: bool = Field(default=False, json_schema_extra={"env": "NATS_ENABLED"})
    nats_url: Optional[str] = Field(default=None, json_schema_extra={"env": "NATS_URL"})
    nats_queue: Optional[str] = Field(
        default="conversa_worker_all", json_schema_extra={"env": "NATS_QUEUE"}
    )
    nats_subjects: str = Field(
        default="com.mylinden.>", json_schema_extra={"env": "NATS_SUBJECTS"}
    )
    nats_stream_name: str = Field(
        default="EVT_LINDEN", json_schema_extra={"env": "NATS_STREAM_NAME"}
    )
    db_app_name: str = Field(
        default="conversa-api", json_schema_extra={"env": "DB_APP_NAME"}
    )
    algolia_app_id: Optional[str] = Field(
        default=None, json_schema_extra={"env": "ALGOLIA_APP_ID"}
    )
    algolia_api_key: Optional[str] = Field(
        default=None, json_schema_extra={"env": "ALGOLIA_API_KEY"}
    )
    typesense_host: Optional[str] = Field(
        default=None, json_schema_extra={"env": "TYPESENSE_HOST"}
    )
    typesense_api_key: Optional[str] = Field(
        default=None, json_schema_extra={"env": "TYPESENSE_API_KEY"}
    )
    typesense_port: int = Field(
        default=443, json_schema_extra={"env": "TYPESENSE_PORT"}
    )

    # Conversa / Telegram
    telegram_enabled: bool = Field(
        default=False, json_schema_extra={"env": "TELEGRAM_ENABLED"}
    )
    telegram_bot_token: Optional[str] = Field(
        default=None, json_schema_extra={"env": "TELEGRAM_BOT_TOKEN"}
    )
    telegram_webhook_secret: Optional[str] = Field(
        default=None, json_schema_extra={"env": "TELEGRAM_WEBHOOK_SECRET"}
    )
    conversa_rate_limit_per_user_per_minute: Optional[int] = Field(
        default=None,
        json_schema_extra={"env": "CONVERSA_RATE_LIMIT_PER_USER_PER_MINUTE"},
    )

    # Session expiry (daily / idle)
    session_expiry_mode: str = Field(
        default="off",
        json_schema_extra={"env": "SESSION_EXPIRY_MODE"},
    )
    session_expiry_at_hour: int = Field(
        default=4,
        ge=0,
        le=23,
        json_schema_extra={"env": "SESSION_EXPIRY_AT_HOUR"},
    )
    session_expiry_idle_minutes: Optional[int] = Field(
        default=None,
        json_schema_extra={"env": "SESSION_EXPIRY_IDLE_MINUTES"},
    )

    # LLM / LiteLLM
    llm_model: str = Field(
        default="gpt-4o-mini", json_schema_extra={"env": "LLM_MODEL"}
    )
    litellm_api_key: Optional[str] = Field(
        default=None, json_schema_extra={"env": "LITELLM_API_KEY"}
    )
    litellm_api_base: Optional[str] = Field(
        default=None, json_schema_extra={"env": "LITELLM_API_BASE"}
    )

    @model_validator(mode="before")
    def set_database_url(cls, values):
        """Set the database_url dynamically based on the environment field."""
        environment = values.get("environment", os.getenv("ENV", "development"))
        if environment.lower() == "test":
            values["database_url"] = os.getenv(
                "TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL
            )
        else:
            values["database_url"] = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

        return values

    @property
    def is_production(self) -> bool:
        """Check if the current environment is production."""
        return self.environment.lower() == "production"

    @property
    def is_test(self) -> bool:
        """Check if the current environment is test."""
        return self.environment.lower() == "test"

    @property
    def database_url_obj(self) -> URL:
        """Return the database URL as a URL object using sqlalchemy's make_url."""
        if not self.database_url:
            raise ValueError("Database URL is not set.")
        return make_url(self.database_url)

    class ConfigDict:
        env_file = str(_PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "allow"  # Allow extra environment variables


def get_settings() -> Settings:
    """Get application settings with required environment variables."""
    return Settings()
