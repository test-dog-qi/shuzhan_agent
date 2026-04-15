"""
MCP模块

所有MCP能力直接集成到代码中，不依赖外部编辑器

架构模式：MCP Gateway / Service Mesh for Tools
- MCPToolProxy: Agent的统一工具调用入口
- MCPClientManager: 底层的多服务器客户端管理器
- 支持多种传输模式：HTTP Streamable、Stdio、SSE
"""

from .base import MCPServer, MCPClient
from .playwright_integration import BrowserAutomation, VisionCaptchaSolver
from .mcp_client_manager import (
    MCPToolProxy,
    MCPClientManager,
    MCPHTTPClient,
    MCPStdioClient,
    TransportType
)
from .mcp_registry import MCPGateway, create_mcp_gateway
from . import http_mcp
from . import login_mcp

__all__ = [
    # 核心
    "MCPServer",
    "MCPClient",
    # Playwright集成（不依赖外部MCP）
    "BrowserAutomation",
    "VisionCaptchaSolver",
    # 统一MCP管理
    "MCPToolProxy",
    "MCPClientManager",
    "MCPHTTPClient",
    "MCPStdioClient",
    "TransportType",
    "MCPGateway",
    "create_mcp_gateway",
    # FastMCP服务器
    "http_mcp",
    "login_mcp",
]
