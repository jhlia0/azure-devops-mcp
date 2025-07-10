import asyncio
from server import mcp


async def main():
    """Main entry point for the Azure DevOps MCP Server."""
    print("Starting Azure DevOps MCP Server...")
    
    # Run the FastMCP server
    await mcp.run()


if __name__ == "__main__":
    # asyncio.run(main())
    mcp.run(transport="sse")
