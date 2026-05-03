
"""
MCP Protocol Support - References OpenClaw's MCP integration
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP Tool definition"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Optional[Callable] = None


@dataclass
class MCPServer:
    """MCP Server configuration"""
    name: str
    transport: str = "stdio"
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)


class MCPClient:
    """
    MCP Protocol Client
    References OpenClaw's MCP integration
    """

    def __init__(self):
        self._servers: Dict[str, MCPServer] = {}
        self._tools: Dict[str, MCPTool] = {}
        self._connected = False

    def add_server(self, server: MCPServer):
        self._servers[server.name] = server

    def list_servers(self) -> List[MCPServer]:
        return list(self._servers.values())

    async def connect(self, server_name: str) -> bool:
        """Connect to MCP server"""
        server = self._servers.get(server_name)
        if not server:
            logger.error(f"Server not found: {server_name}")
            return False

        logger.info(f"Connecting to MCP server: {server_name}")
        return True

    async def list_tools(self, server_name: Optional[str] = None) -> List[MCPTool]:
        """List available tools from MCP servers"""
        return list(self._tools.values())

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """Call an MCP tool"""
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        if tool.handler:
            if asyncio.iscoroutinefunction(tool.handler):
                return await tool.handler(**arguments)
            return tool.handler(**arguments)

        raise NotImplementedError(f"No handler for tool: {tool_name}")

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Optional[Callable] = None,
    ):
        """Register a local tool as MCP tool"""
        self._tools[name] = MCPTool(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
        )


def create_mcp_client() -> MCPClient:
    """Create MCP client instance"""
    return MCPClient()
