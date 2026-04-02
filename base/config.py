from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ServerConfig(BaseModel):
    """Base configuration schema for all MCP servers."""

    # Strict model behaviour: disallow unknown keys, support alias population by field name.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # Shared settings across server types
    name: str
    version: str = "0.1.0"
    description: str = ""
    instructions: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class ApiServerConfig(ServerConfig):
    """Configuration for REST API-backed MCP servers."""

    base_url: HttpUrl  # Required API base endpoint
    auth_token: str | None = None  # Optional bearer token
    default_headers: dict[str, str] = Field(default_factory=dict)  # Optional per-request headers
    timeout_seconds: float = Field(default=30.0, gt=0)  # HTTP client timeout
    max_retries: int = Field(default=2, ge=0, le=10)  # Retry policy for transient failures


class DatabaseServerConfig(ServerConfig):
    dsn: str
    username: str | None = None
    password: str | None = None
    database: str | None = None
    pool_size: int = Field(default=5, ge=1)
    connect_timeout_seconds: float = Field(default=15.0, gt=0)
