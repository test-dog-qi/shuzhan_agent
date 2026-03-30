"""MCP Server基类"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class MCPServer(ABC):
    """
    MCP Server基类

    MCP (Model Context Protocol) Server 提供工具能力给Agent调用
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行MCP工具

        Args:
            tool: 工具名称
            params: 工具参数

        Returns:
            执行结果
        """
        pass

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取支持的工具列表

        子类实现，返回工具定义列表
        """
        return []


class MCPClient:
    """
    MCP Client - 用来调用MCP Server

    支持两种模式：
    1. 本地模式 - 直接实例化MCP Server调用
    2. 远程模式 - 通过HTTP调用远程MCP Server
    """

    def __init__(self, server: MCPServer):
        self.server = server

    async def call(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """调用MCP工具"""
        return await self.server.execute(tool, params)
