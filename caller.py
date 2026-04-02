import asyncio
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        result = await client.call_tool(
            name="server_info",
            arguments={"endpoint": "posts"}
        )
    print(result)

asyncio.run(main())