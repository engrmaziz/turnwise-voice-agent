"""Typed process settings. Thresholds and endpoints live here, not in call sites."""

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class Settings(BaseSettings):
    """Environment-backed settings for one Turnwise process.

    ``TURNWISE_`` is the env prefix. An empty ``TURNWISE_PII_HASH_KEY`` is treated
    as unset so a blank ``.env`` line does not become a shared hash salt.
    """

    model_config = SettingsConfigDict(
        env_prefix="TURNWISE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    service_name: str = "turnwise"
    log_level: str = "INFO"
    log_json: bool = False
    http_host: str = "127.0.0.1"
    http_port: int = 8000
    stage_queue_maxsize: int = 32
    stage_put_timeout_s: float = 0.25
    otel_enabled: bool = True
    otel_endpoint: str = "http://localhost:4317"
    otel_insecure: bool = True
    otel_export_timeout_s: float = 5.0
    otel_max_queue_size: int = 2048
    metrics_enabled: bool = True
    pii_hash_key: SecretStr | None = None
    pii_fields: str = "patient_name,name,dob,date_of_birth,phone"

    @field_validator("service_name", "otel_endpoint")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be non-empty")
        return stripped

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in _LOG_LEVELS:
            raise ValueError("log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @field_validator("pii_hash_key", mode="before")
    @classmethod
    def blank_pii_key_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("http_port")
    @classmethod
    def port_in_range(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("http_port must be between 1 and 65535")
        return value

    @field_validator("stage_queue_maxsize", "otel_max_queue_size")
    @classmethod
    def at_least_one(cls, value: int) -> int:
        if value < 1:
            raise ValueError("queue sizes must be >= 1")
        return value

    @field_validator("stage_put_timeout_s", "otel_export_timeout_s")
    @classmethod
    def positive_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("timeouts must be > 0")
        return value

    @property
    def pii_field_names(self) -> frozenset[str]:
        return frozenset(part.strip() for part in self.pii_fields.split(",") if part.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process settings, cached so the ASGI app and ``python -m server`` share one object."""
    return Settings()
