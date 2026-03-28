from __future__ import annotations

import functools
import os
from typing import Any, Dict, Iterable

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Troll-E API"
    environment: str = "development"
    secret_key: str = "changeme"

    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/trolle"
    redis_url: str = "redis://redis:6379/0"

    api_cache_ttl_seconds: int = 600
    default_radius_km: float = 2.0

    # CORS configuration
    cors_origins: str = "*"

    feature_enabled_chains: Dict[str, bool] = Field(default_factory=dict)

    admin_username: str = "admin"
    admin_password: str = "admin"

    # Embedding / pgvector
    embedding_enabled: bool = False
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Alerting
    alert_webhook_url: str = ""
    stale_threshold_hours: float = 36.0

    # Sentry
    sentry_dsn: str = ""

    # Cache TTLs (seconds)
    cache_ttl_product_list: int = 300
    cache_ttl_product_detail: int = 600
    cache_ttl_stores_nearby: int = 3600
    cache_ttl_trolley_compare: int = 300
    cache_ttl_recipe_list: int = 1800
    cache_ttl_recipe_cost: int = 300

    # Database pool
    db_pool_size: int = 15
    db_max_overflow: int = 15
    db_pool_timeout: int = 10

    # Supabase Auth
    supabase_url: str = ""

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate SECRET_KEY meets security requirements."""
        insecure_defaults = [
            "changeme",
            "change-me",
            "dev-secret",
            "secret",
            "password",
            "admin",
        ]

        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters long (current: {len(v)}). "
                "Generate a secure key with: openssl rand -base64 32"
            )

        if v.lower() in insecure_defaults:
            raise ValueError(
                "SECRET_KEY cannot be a default value. "
                "Generate a secure key with: openssl rand -base64 32"
            )

        return v

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Ensure Redis URL contains a password in production."""
        env = os.environ.get("ENVIRONMENT", "development")
        if env == "production" and "redis://:@" in v:
            raise ValueError(
                "REDIS_URL must include a password in production. "
                "Set REDIS_PASSWORD in your environment."
            )
        return v

    admin_password_hash: str = ""

    @field_validator("admin_password")
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        """Reject weak admin passwords in production."""
        env = os.environ.get("ENVIRONMENT", "development")
        weak_defaults = ["admin", "password", "changeme"]

        if env == "production":
            if v in weak_defaults:
                raise ValueError(
                    "ADMIN_PASSWORD cannot be a default value in production."
                )
            if len(v) < 12:
                raise ValueError(
                    f"ADMIN_PASSWORD must be at least 12 characters in production (current: {len(v)})."
                )
        else:
            if v in weak_defaults:
                import warnings
                warnings.warn(
                    "Using default admin password. Change this in production!",
                    UserWarning,
                )

        return v

    @field_validator("feature_enabled_chains", mode="before")
    @classmethod
    def _parse_feature_flags(cls, value: Any) -> Dict[str, bool]:
        if not value:
            return {}
        if isinstance(value, dict):
            return {str(k): bool(v) for k, v in value.items()}
        if isinstance(value, str):
            items: Iterable[str] = value.split(",")
            result: Dict[str, bool] = {}
            for item in items:
                if not item:
                    continue
                key, _, raw = item.partition(":")
                result[key.strip()] = raw.strip().lower() in {"1", "true", "yes"}
            return result
        raise ValueError("Unsupported feature flag format")


@functools.lru_cache()
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
