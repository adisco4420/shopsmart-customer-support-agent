"""Entry point for running the MCP server as a module: python -m src.mcp_server"""

from src.mcp_server.server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
