import httpx
from fastmcp import FastMCP

from base.base import BaseMCPServer
from base.config import ApiServerConfig
from base.errors import MCPServerError


class DummyAPIMCPServer(BaseMCPServer):
    """MCP server implementation for calling a REST endpoint via httpx client."""

    def __init__(self, config: ApiServerConfig):
        """Initialize base MCP server config and placeholder AsyncClient."""
        super().__init__(config)
        self.client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        """Set up async httpx client at startup (before service handles requests)."""
        await super().startup()
        self.client = httpx.AsyncClient(
            base_url=str(self.config.base_url),
            timeout=self.config.timeout_seconds,
            headers=self.config.default_headers,
        )

    async def shutdown(self) -> None:
        """Cleanly close the httpx client on shutdown to release resources."""
        if self.client:
            await self.client.aclose()
        await super().shutdown()

    def register_tools(self, mcp: FastMCP) -> None:
        """Register tool endpoints available through FastMCP agent calls."""

        @mcp.tool
        async def get_data(endpoint: str) -> dict:
            """Fetch data from the remote API path relative to base_url."""
            if self.client is None:
                raise MCPServerError("HTTP client not initialized")
            try:
                response = await self.client.get(endpoint)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                raise self.normalize_exception(e)

        @mcp.tool
        async def post_data(endpoint: str, payload: dict) -> dict:
            """Send JSON payload to the remote API path relative to base_url."""
            if self.client is None:
                raise MCPServerError("HTTP client not initialized")
            try:
                response = await self.client.post(endpoint, json=payload)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                raise self.normalize_exception(e)
            

if __name__ == "__main__":
    config = ApiServerConfig(
    name="dummy-api-server",
    description="Dummy REST API MCP Server",
    base_url="https://jsonplaceholder.typicode.com",
  
    
    )

    api_server = DummyAPIMCPServer(config)
    api_server.run(transport="http")
    
