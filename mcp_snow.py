import os
import sys
from typing import List, Optional, Dict, Any

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
if _ROOT_DIR not in sys.path:
    sys.path.append(_ROOT_DIR)

import dotenv
dotenv.load_dotenv(dotenv_path=".env")

import fastmcp
fastmcp.settings.port = os.getenv("SNOW_MCP_PORT", 9901)
fastmcp.settings.host = os.getenv("SNOW_MCP_HOST","0.0.0.0")
fastmcp.settings.log_enabled = True

import httpx
from fastmcp import FastMCP
from base.base import BaseMCPServer
from base.config import ServiceNowConfig
from base.logging import get_logger
logger = get_logger(name=__name__)





from connectors.snow_connector import aggregate, get_table



# from fastmcp.server.auth.providers.introspection import IntrospectionTokenVerifier
# SCOPES = ["profile"]
# token_verifier = IntrospectionTokenVerifier(
#     introspection_url="",
#     client_id="",
#     client_secret="",
#     required_scopes=SCOPES
# )


class ServiceNowMcpServer(BaseMCPServer):
    def __init__(self, config:ServiceNowConfig ):
        
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
    

    def register_tools(self, mcp: FastMCP) -> dict:
        """Register tool endpoints available through FastMCP agent calls."""


        # aggregate method 
        @mcp.tool
        async def service_now_aggregate(
        table_name: str,
        sysparm_query: str,
        sysparm_group_by: str,
        sysparm_avg_fields: list[str] | None = None,
        sysparm_max_fields: list[str] | None = None,
        sysparm_min_fields: list[str] | None = None,
        sysparm_sum_fields: list[str] | None = None,
        sysparm_display_value: str = "true",
        sysparm_count: bool = True,) -> dict:
            """
            Retrieve records from a ServiceNow table and perform aggregate operations.

            Use this when aggregate results are required (count, min, max, avg, sum).

            Args:
                table_name: Name of the table (e.g., 'incident', 'cmdb_ci_server')
                sysparm_query: Filter and sort expression.
                    - Filters are defined as: field operator value
                    - Default operator is '='
                    - Use LIKE for contains (without % wildcards)
                    - Sorting: ORDERBYfield or ORDERBYDESCfield
                sysparm_group_by: Field(s) to group results by
                sysparm_avg_fields: Fields for average calculation
                sysparm_max_fields: Fields for maximum calculation
                sysparm_min_fields: Fields for minimum calculation
                sysparm_sum_fields: Fields for sum calculation
                sysparm_display_value: Whether to return display values ("true"/"false")
                sysparm_count: Whether to include record count

            Returns:
                dict: Aggregated response or error details
            """


            if not table_name:
                raise ValueError("table_name is required")

            try:
                return await aggregate(
                    table_name,
                    sysparm_group_by,
                    sysparm_avg_fields,
                    sysparm_max_fields,
                    sysparm_min_fields,
                    sysparm_sum_fields,
                    sysparm_query,
                    sysparm_display_value,
                    sysparm_count,
                )

            except Exception as e:
                logger.exception(f"ServiceNow aggregate failed for table '{table_name}': {e}")
                return {
                    "error": str(e),
                    "table_name": table_name,
                }
    
        # service now get table generic 
        @mcp.tool
        async def service_now_get_table(
            table_name: str,
            sysparm_query: Optional[str] = None,
            limit: Optional[int] = 200,
        ) -> Dict[str, Any]:
            """
            Retrieve records from a ServiceNow table.

            This is a generic wrapper around the ServiceNow Table API that allows
            querying any table with optional filters and row limits.

            Args:
                table_name:
                    Name of the ServiceNow table to query
                    (e.g., 'incident', 'cmdb_ci_server').

                sysparm_query:
                    ServiceNow query expression used for filtering and sorting.

                    Query format rules:
                    - Conditions follow: <field><operator><value>
                    Example: "priority=1^active=true"
                    - Default operator is '='
                    - Use LIKE for contains searches (do NOT include % wildcards)
                    Example: "short_descriptionLIKEemail"
                    - Multiple conditions are joined with '^'
                    - Sorting:
                        ORDERBY<field>
                        ORDERBYDESC<field>

                limit:
                    Maximum number of records to return.

                    - Must be a positive integer if provided
                    - None uses ServiceNow instance default
                    - Caller is responsible for respecting API caps

            Returns:
                Dict[str, Any]:
                    - Raw ServiceNow JSON response on success
                    - Error dictionary if the request fails
            """

            if not table_name:
                raise ValueError("table_name is required")

            if limit is not None:
                limit = int(limit)
                if limit <= 0:
                    raise ValueError("limit must be a positive integer")

            try:
                data = await get_table(table_name, sysparm_query, limit)
                return data or {"error": "No data returned from ServiceNow"}

            except Exception as e:  # intentionally broad for tool-safe responses
                logger.exception("service_now_get_table failed")
                return {"error": str(e)}
            
        @mcp.tool
        async def service_now_get_user_details(
            table_name: str = "sys_user",
            sysparm_query: Optional[str] = None,
            limit: Optional[int] = 200,
            ) -> Dict[str, Any]:
            """
            Retrieve user records from ServiceNow.

            This method queries the ServiceNow Table API (default: sys_user) and
            returns matching user details based on an optional query filter.

            Args:
                table_name:
                    Name of the ServiceNow table to query.
                    Defaults to "sys_user".

                sysparm_query:
                    ServiceNow query expression used for filtering and sorting.

                    Query format rules:
                    - Conditions: <field><operator><value>
                    Example: "active=true^nameLIKEJohn"
                    - Default operator is '='
                    - Use LIKE for contains searches (no % wildcards)
                    - Multiple conditions separated by '^'
                    - Sorting:
                        ORDERBY<field>
                        ORDERBYDESC<field>

                    Examples:
                        "active=true"
                        "department=IT^ORDERBYname"
                        "nameLIKEJohn^active=true"

                limit:
                    Maximum number of records to return.

                    - Must be a positive integer if provided
                    - None uses ServiceNow instance default
                    - Values above API caps may be truncated

            Returns:
                Dict[str, Any]:
                    Raw ServiceNow JSON response on success, or
                    an error dictionary if the request fails.
            """

            if not table_name:
                raise ValueError("table_name is required")

            if limit is not None:
                limit = int(limit)
                if limit <= 0:
                    raise ValueError("limit must be a positive integer")
                if limit > 200:  # defensive cap
                    limit = 200

            try:
                data = await get_table(table_name, sysparm_query, limit)
                return data or {"error": "No data returned from ServiceNow"}

            except Exception as e:  # intentionally broad for tool-safe response
                logger.exception("service_now_get_user_details failed")
                return {"error": str(e)}


if __name__ == "__main__":

    config = ServiceNowConfig(
    name="service_now_mcp",
    description="service_now_mcp_server",
    base_url="",
    )

    mcp = ServiceNowMcpServer(config=config)
    mcp.run(transport='streamable-http', port=9901, host="0.0.0.0")
