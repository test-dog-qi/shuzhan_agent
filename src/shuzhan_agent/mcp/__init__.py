"""
MCP模块

所有MCP能力直接集成到代码中，不依赖外部编辑器
"""

from .base import MCPServer, MCPClient
from .datastack_mcp import DataStackMCP, OFFLINE_MODULES, MODULE_DEPENDENCIES
from .auth import DataStackAuthenticator, DataStackAuth, AuthManager, AuthResult, CaptchaHandler
from .playwright_integration import BrowserAutomation, VisionCaptchaSolver

__all__ = [
    # 核心
    "MCPServer",
    "MCPClient",
    # 数栈API
    "DataStackMCP",
    "OFFLINE_MODULES",
    "MODULE_DEPENDENCIES",
    # 认证
    "DataStackAuthenticator",
    "DataStackAuth",
    "AuthManager",
    "AuthResult",
    "CaptchaHandler",
    # Playwright集成（不依赖外部MCP）
    "BrowserAutomation",
    "VisionCaptchaSolver",
]
