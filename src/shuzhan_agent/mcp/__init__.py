"""
MCP模块

提供MCP客户端封装，调用外部MCP Server的能力
"""

from .base import MCPServer, MCPClient
from .datastack_mcp import DataStackMCP, OFFLINE_MODULES, MODULE_DEPENDENCIES
from .auth import DataStackAuthenticator, AuthManager, AuthResult, CaptchaHandler
from .captcha_solver import CaptchaSolver, MCPCaptchaSolver, CaptchaSolverFactory, CAPTCHA_MCP_SERVERS

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
    "AuthManager",
    "AuthResult",
    "CaptchaHandler",
    # 验证码
    "CaptchaSolver",
    "MCPCaptchaSolver",
    "CaptchaSolverFactory",
    "CAPTCHA_MCP_SERVERS",
]
