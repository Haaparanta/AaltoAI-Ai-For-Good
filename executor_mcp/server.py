"""MCP executor server composing all workspace tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from executor_mcp import api_signatures, execute_command, read_file, write_file
from executor_mcp.paths import get_workspace_root

mcp = FastMCP("executor")


def main() -> None:
    """Start the stdio MCP server with all executor tools registered."""
    root = get_workspace_root()
    read_file.register(mcp, root)
    write_file.register(mcp, root)
    execute_command.register(mcp, root)
    api_signatures.register(mcp, root)
    mcp.run()


if __name__ == "__main__":
    main()
