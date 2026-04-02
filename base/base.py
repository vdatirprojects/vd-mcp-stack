from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from .config import ServerConfig
from .errors import MCPServerError
from .logging import get_logger


class BaseMCPServer(ABC):
    """Base class for MCP (Multi-Chain Provider) servers."""

    def __init__(self, config: ServerConfig) -> None:
        """Initialize core components for the MCP server."""
        self.config = config
        self.logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._mcp: FastMCP | None = None

    def build_server(self) -> FastMCP:
        """Create and configure FastMCP instance once (lazy initialization)."""
        if self._mcp is None:
            self._mcp = FastMCP(
                name=self.config.name,
                instructions=self.config.instructions,
                lifespan=self._lifespan,
            )
            self.register_tools(self._mcp)
            self.register_resources(self._mcp)
            self.register_prompts(self._mcp)
        return self._mcp

    @property
    def mcp(self) -> FastMCP:
        """Shortcut property to access the built MCP server instance."""
        return self.build_server()

    @asynccontextmanager
    async def _lifespan(self, _server: FastMCP):
        """Lifespan context manager used by FastMCP to handle startup/shutdown."""
        await self.startup()
        try:
            yield {"config": self.config.model_dump()}
        except Exception as exc:  # pragma: no cover - defensive
            raise self.normalize_exception(exc) from exc
        finally:
            await self.shutdown()

    def normalize_exception(self, exc: Exception) -> MCPServerError:
        """Convert generic exceptions into MCPServerError for uniform error handling."""
        if isinstance(exc, MCPServerError):
            return exc
        return MCPServerError(str(exc), cause=exc)

    async def startup(self) -> None:
        """Hook for server startup, can be overridden by subclasses."""
        self.logger.info("Starting %s", self.config.name)

    async def shutdown(self) -> None:
        """Hook for server shutdown, can be overridden by subclasses."""
        self.logger.info("Stopping %s", self.config.name)

    @abstractmethod
    def register_tools(self, mcp: FastMCP) -> None:
        """Register user-defined tools for this MCP server instance."""
        raise NotImplementedError

    def register_resources(self, mcp: FastMCP) -> None:
        """Register built-in resources accessible by the MCP runtime."""

        @mcp.resource("resource://server/info")
        async def server_info() -> dict[str, Any]:
            """Return basic metadata about the running MCP server."""
            return {
                "name": self.config.name,
                "version": self.config.version,
                "description": self.config.description,
                "settings": self.config.settings,
            }

    def register_prompts(self, mcp: FastMCP) -> None:
        """Register common prompts that can guide agent behavior in each session."""

        @mcp.prompt
        def server_usage_prompt(goal: str) -> str:
            """A default prompt instructing agents to check server tools and resources."""
            return (
                f"You are using the {self.config.name} MCP server. "
                f"Goal: {goal}. Review available tools, resources, and prompts before acting."
            )

    def create_server(self) -> FastMCP:
        """Alias for build_server for compatibility with alternative APIs."""
        return self.build_server()

    def run(self, **kwargs: Any) -> None:
        """Run the built MCP server with runtime kwargs (e.g., transport)."""
        self.build_server().run(**kwargs)
