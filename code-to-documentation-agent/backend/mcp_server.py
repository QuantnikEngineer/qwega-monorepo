from fastmcp import FastMCP
from main import app
import asyncio

mcp = FastMCP.from_fastapi(
            app=app,
            name="Functional Test MCP Server",
            version="0.1.0",
    )

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8007)