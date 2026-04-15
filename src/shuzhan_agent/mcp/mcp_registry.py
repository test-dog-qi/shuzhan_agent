"""
MCP注册器 - 统一管理本地和远程MCP服务器

架构说明：
- 本地服务器：通过 FastMCP 运行，通过 stdio 传输连接
- 远程服务器：通过 HTTP Streamable 传输连接

使用示例：
```python
from shuzhan_agent.mcp import MCPGateway

gateway = MCPGateway()

# 方式1：添加本地FastMCP服务器（通过stdio连接）
gateway.add_local_server("http", "from shuzhan_agent.mcp.http_mcp import http_mcp")
gateway.add_local_server("login", "from shuzhan_agent.mcp.login_mcp import login_mcp")

# 方式2：添加远程HTTP MCP服务器
gateway.add_remote_server("context7", "https://context7.io/mcp")

# 初始化所有服务器
await gateway.initialize()

# 获取所有工具
tools = gateway.list_tools()

# Agent调用
result = await gateway.call_tool("http", "POST", {...})
```
"""

import os
import asyncio
import subprocess
import json
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

from shuzhan_agent.mcp.mcp_client_manager import (
    MCPServerConfig,
    MCPClientManager,
    TransportType,
    ToolCallResult
)

logger = logging.getLogger(__name__)


@dataclass
class LocalServerConfig:
    """本地MCP服务器配置"""
    name: str                          # 服务器名称
    module_path: str                   # 模块路径，如 "shuzhan_agent.mcp.http_mcp"
    object_name: str                   # FastMCP实例名，如 "http_mcp"
    command: str = "fastmcp"            # 启动命令
    env: Dict[str, str] = field(default_factory=dict)  # 环境变量


@dataclass
class RemoteServerConfig:
    """远程MCP服务器配置"""
    name: str                          # 服务器名称
    url: str                           # 服务器URL
    headers: Dict[str, str] = field(default_factory=dict)  # HTTP headers


class MCPGateway:
    """
    MCP网关 - 统一管理本地和远程MCP服务器

    支持两种服务器类型：
    1. LocalServer: 本地FastMCP服务器，通过stdio连接
    2. RemoteServer: 远程MCP服务器，通过HTTP Streamable连接
    """

    def __init__(self):
        self._manager = MCPClientManager()
        self._local_servers: Dict[str, subprocess.Popen] = {}
        self._initialized = False

    def add_local_server(
        self,
        name: str,
        module_path: str,
        object_name: str = None,
        command: str = "fastmcp",
        args: List[str] = None,
        env: Dict[str, str] = None
    ) -> "MCPGateway":
        """
        添加本地MCP服务器

        Args:
            name: 服务器名称（唯一标识）
            module_path: 模块路径，如 "shuzhan_agent.mcp.http_mcp"
            object_name: FastMCP实例名，如 "http_mcp"（默认取模块名的最后部分）
            command: 启动命令，默认 "fastmcp"
            args: 命令参数，默认 ["run", module_path, object_name]
            env: 环境变量

        Example:
            gateway.add_local_server("http", "shuzhan_agent.mcp.http_mcp")
            gateway.add_local_server("login", "shuzhan_agent.mcp.login_mcp", "login_mcp")
        """
        if object_name is None:
            # 从模块路径推断，如 "shuzhan_agent.mcp.http_mcp" -> "http_mcp"
            object_name = module_path.split(".")[-1]

        # 使用提供的args或构建默认的
        server_args = args if args is not None else ["run", module_path, object_name]

        config = MCPServerConfig(
            name=name,
            transport=TransportType.STDIO,
            command=command,
            args=server_args,
            env=env or {}
        )

        self._manager.add_server(config)
        return self

    def add_remote_server(
        self,
        name: str,
        url: str,
        headers: Dict[str, str] = None
    ) -> "MCPGateway":
        """
        添加远程MCP服务器

        Args:
            name: 服务器名称（唯一标识）
            url: 服务器URL，如 "https://context7.io/mcp"
            headers: HTTP headers（如认证信息）

        Example:
            gateway.add_remote_server("context7", "https://context7.io/mcp", {
                "Authorization": "Bearer xxx"
            })
        """
        config = MCPServerConfig(
            name=name,
            transport=TransportType.HTTP,
            url=url,
            headers=headers or {}
        )

        self._manager.add_server(config)
        return self

    async def initialize(self) -> Dict[str, bool]:
        """
        初始化所有MCP服务器连接

        对于本地服务器，会启动子进程
        对于远程服务器，会建立HTTP连接

        Returns:
            {server_name: success} 的字典
        """
        if self._initialized:
            return {name: True for name in self._manager.get_servers()}

        results = await self._manager.initialize_all()

        # 启动本地stdio服务器的子进程
        for name, config in [(n, s.config) for n, s in self._manager._servers.items()]:
            if config.transport == TransportType.STDIO:
                await self._start_local_server(name, config)

        self._initialized = True

        return results

    async def _start_local_server(self, name: str, config: MCPServerConfig):
        """启动本地stdio服务器子进程"""
        try:
            process = subprocess.Popen(
                [config.command] + config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **config.env}
            )
            self._local_servers[name] = process
            logger.info(f"本地MCP服务器 {name} 已启动 (PID: {process.pid})")
        except Exception as e:
            logger.error(f"启动本地MCP服务器 {name} 失败: {e}")

    def list_tools(self) -> List[Dict[str, Any]]:
        """获取所有聚合的工具列表"""
        return self._manager.list_tools()

    def get_tools_by_server(self, server_name: str) -> List[Dict[str, Any]]:
        """获取指定服务器的工个列表"""
        return self._manager.get_tools_by_server(server_name)

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """
        调用指定服务器的指定工具

        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具调用结果
        """
        return await self._manager.call_tool(server_name, tool_name, arguments)

    async def call_tool_by_name(self, tool_name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """
        根据工具名自动路由调用

        Args:
            tool_name: 工具名称（会在所有服务器中查找）
            arguments: 工具参数

        Returns:
            工具调用结果
        """
        return await self._manager.call_tool_by_name(tool_name, arguments)

    def get_servers(self) -> List[str]:
        """获取所有已注册的服务器名称"""
        return self._manager.get_servers()

    async def close(self):
        """关闭所有服务器连接"""
        # 关闭本地子进程
        for name, process in self._local_servers.items():
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            logger.info(f"本地MCP服务器 {name} 已关闭")

        self._local_servers.clear()
        self._manager.close_all()
        self._initialized = False


# 预定义的远程MCP服务器
REMOTE_MCP_SERVERS = {
    "context7": {
        "name": "context7",
        "url": "https://context7.io/mcp",  # 示意URL，实际需要从context7获取
        "description": "Context7文档检索MCP服务器",
        "headers": {}
    },
    # 未来可以添加更多远程服务器
    # "github": {
    #     "name": "github",
    #     "url": "https://api.github.com/mcp",
    #     "description": "GitHub API MCP服务器",
    #     "headers": {"Authorization": "Bearer xxx"}
    # }
}


def create_mcp_gateway(
    local_servers: List[Dict[str, str]] = None,
    remote_servers: List[str] = None
) -> MCPGateway:
    """
    创建配置好的MCP网关

    Args:
        local_servers: 本地服务器配置列表
            [{"name": "http", "module": "shuzhan_agent.mcp.http_mcp"}, ...]
            可选字段: object, command, args, env
        remote_servers: 远程服务器名称列表（使用预配置）
            ["context7", ...]

    Returns:
        配置好的MCPGateway实例
    """
    gateway = MCPGateway()

    # 添加本地服务器
    if local_servers:
        for server in local_servers:
            gateway.add_local_server(
                name=server["name"],
                module_path=server["module"],
                object_name=server.get("object"),
                command=server.get("command", "fastmcp"),
                args=server.get("args"),
                env=server.get("env", {})
            )

    # 添加远程服务器
    if remote_servers:
        for server_name in remote_servers:
            if server_name in REMOTE_MCP_SERVERS:
                config = REMOTE_MCP_SERVERS[server_name]
                gateway.add_remote_server(
                    name=config["name"],
                    url=config["url"],
                    headers=config.get("headers", {})
                )
            else:
                logger.warning(f"未知的远程服务器: {server_name}")

    return gateway
