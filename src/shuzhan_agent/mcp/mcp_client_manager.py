"""
MCP客户端管理器 - 优化后的架构

层级简化：
- 层级1: MCPToolProxy.call()     - 统一入口
- 层级2: MCPClientManager.call_tool() - 直接路由
- 层级3: MCPStdioClient.call_tool()  - 通信协议
- 层级4: POST/GET 工具              - 业务实现
"""

import os
import json
import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

import httpx

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """传输类型枚举"""
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    server_name: str
    input_schema: Dict[str, Any]


@dataclass
class ToolCallResult:
    """工具调用结果"""
    success: bool
    result: Any
    error: Optional[str] = None
    server_name: str = ""


@dataclass
class MCPServerConfig:
    """MCP服务器配置（保留用于兼容）"""
    name: str
    transport: TransportType
    url: str = ""
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30


# ============================================================================
# 层级3: 通信协议层 - MCPStdioClient
# ============================================================================

class MCPStdioClient:
    """MCP Stdio 客户端（子进程模式）"""

    def __init__(self, command: str, args: List[str] = None, env: Dict[str, str] = None, timeout: int = 30):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.timeout = timeout
        self._request_queue: Optional[asyncio.Queue] = None
        self._response_queue: Optional[asyncio.Queue] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._initialized = False
        self._closed = False

    async def initialize(self) -> bool:
        """初始化连接"""
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp import ClientSession

        self._request_queue = asyncio.Queue()
        self._response_queue = asyncio.Queue()

        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env={**os.environ, **self.env} if self.env else None,
            timeout=self.timeout
        )

        async def worker():
            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self._initialized = True

                        while not self._closed:
                            try:
                                request = await asyncio.wait_for(
                                    self._request_queue.get(), timeout=1.0
                                )
                            except asyncio.TimeoutError:
                                continue

                            if request is None:
                                break

                            method = request["method"]
                            request_id = request["id"]
                            params = request.get("params", {})

                            try:
                                if method == "list_tools":
                                    result = await session.list_tools()
                                    tools = [
                                        {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
                                        for t in result.tools
                                    ]
                                    await self._response_queue.put({"id": request_id, "result": {"tools": tools}})
                                elif method == "call_tool":
                                    result = await session.call_tool(params["name"], params["arguments"])
                                    await self._response_queue.put({
                                        "id": request_id,
                                        "result": {
                                            "content": [
                                                {"type": "text", "text": c.text} if hasattr(c, 'text') else c
                                                for c in result.content
                                            ]
                                        }
                                    })
                            except Exception as e:
                                await self._response_queue.put({"id": request_id, "error": str(e)})
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"MCP Stdio worker error: {e}")
            finally:
                self._initialized = False

        self._worker_task = asyncio.create_task(worker())

        # 等待初始化
        for _ in range(50):
            await asyncio.sleep(0.1)
            if self._initialized:
                break

        if not self._initialized:
            raise Exception("MCP Stdio 客户端初始化超时")

        logger.info("MCP Stdio 客户端初始化成功")
        return True

    async def _send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """发送请求并等待响应"""
        if not self._request_queue or not self._response_queue:
            raise Exception("客户端未初始化")

        request_id = id(self)
        await self._request_queue.put({"id": request_id, "method": method, "params": params or {}})

        while True:
            try:
                response = await asyncio.wait_for(self._response_queue.get(), timeout=self.timeout)
                if response["id"] == request_id:
                    if "error" in response:
                        raise Exception(response["error"])
                    return response.get("result", {})
            except asyncio.TimeoutError:
                raise Exception(f"MCP request timeout: {method}")

    async def list_tools(self) -> List[ToolDefinition]:
        """获取工具列表"""
        result = await self._send_request("list_tools")
        return [
            ToolDefinition(
                name=t["name"],
                description=t.get("description", ""),
                server_name="",
                input_schema=t.get("input_schema", t.get("inputSchema", {}))
            )
            for t in result.get("tools", [])
        ]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """调用工具"""
        try:
            result = await self._send_request("call_tool", {"name": tool_name, "arguments": arguments})
            content = result.get("content", [])
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    return ToolCallResult(success=True, result=item.get("text", ""), server_name="")
            return ToolCallResult(success=True, result=str(content), server_name="")
        except Exception as e:
            return ToolCallResult(success=False, result=None, error=str(e))

    async def close(self):
        """关闭连接"""
        self._closed = True
        if self._request_queue:
            await self._request_queue.put(None)
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._initialized = False


class MCPHTTPClient:
    """MCP HTTP 客户端"""

    def __init__(self, url: str, headers: Dict[str, str] = None, timeout: int = 30):
        self.url = url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self._session_token = None

    async def _send_request(self, method: str, params: Dict[str, Any], request_id: int = 1) -> Dict[str, Any]:
        """发送 JSON-RPC 请求"""
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": request_id}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def initialize(self) -> bool:
        """初始化"""
        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "shuzhan-agent", "version": "1.0.0"},
            "capabilities": {"tools": {}}
        }, request_id=1)
        if "session" in result:
            self._session_token = result["session"]
            self.headers["MCP-Session-ID"] = self._session_token
        return True

    async def list_tools(self) -> List[ToolDefinition]:
        """获取工具列表"""
        result = await self._send_request("tools/list", {}, request_id=2)
        return [
            ToolDefinition(
                name=t["name"],
                description=t.get("description", ""),
                server_name="",
                input_schema=t.get("inputSchema", t.get("input_schema", {}))
            )
            for t in result.get("result", {}).get("tools", [])
        ]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """调用工具"""
        try:
            result = await self._send_request("tools/call", {"name": tool_name, "arguments": arguments}, request_id=3)
            if "result" in result:
                content = result["result"].get("content", [])
                if content and isinstance(content, list) and content[0].get("type") == "text":
                    return ToolCallResult(success=True, result=content[0].get("text", ""), server_name="")
                return ToolCallResult(success=True, result=str(result["result"]), server_name="")
            elif "error" in result:
                return ToolCallResult(success=False, result=None, error=result["error"].get("message", str(result["error"])), server_name="")
            return ToolCallResult(success=True, result=str(result), server_name="")
        except httpx.HTTPStatusError as e:
            return ToolCallResult(success=False, result=None, error=f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            return ToolCallResult(success=False, result=None, error=str(e))


# ============================================================================
# 层级2: MCPClientManager - 直接管理客户端
# ============================================================================

class MCPClientManager:
    """
    MCP客户端管理器 - 简化后直接管理客户端

    消除了 MCPServerConnection 的透传层
    """

    def __init__(self):
        # 直接存储客户端实例，不再有中间层
        self._clients: Dict[str, MCPStdioClient | MCPHTTPClient] = {}
        self._tools: Dict[str, List[ToolDefinition]] = {}  # server_name -> tools
        self._tool_name_to_server: Dict[str, str] = {}  # tool_name -> server_name

    def add_server(self, name: str = "", transport: TransportType = None, *,
                   url: str = "", command: str = "", args: List[str] = None,
                   env: Dict[str, str] = None, headers: Dict[str, str] = None, timeout: int = 30) -> bool:
        """添加服务器（兼容 MCPServerConfig 和直接参数）"""
        # 支持传入 MCPServerConfig
        if isinstance(name, MCPServerConfig):
            config = name
            name = config.name
            transport = config.transport
            url = config.url
            command = config.command
            args = config.args
            env = config.env
            headers = config.headers
            timeout = config.timeout

        if name in self._clients:
            logger.warning(f"服务器 {name} 已存在，将被替换")
            del self._clients[name]

        if transport == TransportType.STDIO:
            self._clients[name] = MCPStdioClient(command=command, args=args, env=env, timeout=timeout)
        else:  # HTTP or SSE
            self._clients[name] = MCPHTTPClient(url=url, headers=headers or {}, timeout=timeout)

        return True

    def add_stdio_server(self, name: str, command: str, args: List[str] = None, env: Dict[str, str] = None) -> bool:
        """快捷方法：添加stdio服务器"""
        return self.add_server(name, TransportType.STDIO, command=command, args=args, env=env)

    def add_http_server(self, name: str, url: str, headers: Dict[str, str] = None) -> bool:
        """快捷方法：添加HTTP服务器"""
        return self.add_server(name, TransportType.HTTP, url=url, headers=headers)

    async def initialize_all(self) -> Dict[str, bool]:
        """初始化所有服务器"""
        results = {}
        for name, client in self._clients.items():
            try:
                await client.initialize()
                # 获取工具列表
                self._tools[name] = await client.list_tools()
                for tool in self._tools[name]:
                    tool.server_name = name
                    self._tool_name_to_server[tool.name] = name
                results[name] = True
                logger.info(f"MCP服务器 {name} 初始化成功，提供 {len(self._tools[name])} 个工具")
            except Exception as e:
                logger.error(f"初始化MCP服务器 {name} 失败: {e}")
                results[name] = False
        return results

    def list_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具"""
        all_tools = []
        for server_name, tools in self._tools.items():
            for tool in tools:
                all_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "server_name": tool.server_name,
                    "input_schema": tool.input_schema
                })
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """调用指定服务器的指定工具"""
        client = self._clients.get(server_name)
        if not client:
            return ToolCallResult(success=False, result=None, error=f"服务器不存在: {server_name}")

        result = await client.call_tool(tool_name, arguments)
        result.server_name = server_name
        return result

    async def call_tool_by_name(self, tool_name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """根据工具名自动路由"""
        server_name = self._tool_name_to_server.get(tool_name)
        if not server_name:
            return ToolCallResult(success=False, result=None, error=f"未找到工具: {tool_name}")
        return await self.call_tool(server_name, tool_name, arguments)

    def get_servers(self) -> List[str]:
        """获取所有服务器名称"""
        return list(self._clients.keys())

    async def close_all(self):
        """关闭所有连接"""
        for client in self._clients.values():
            if hasattr(client, 'close'):
                await client.close()


# ============================================================================
# 层级1: MCPToolProxy - 统一入口
# ============================================================================

class MCPToolProxy:
    """
    MCP工具代理 - Agent的统一工具接口

    优化后简化为4层调用链：
    1. MCPToolProxy.call() - 统一入口
    2. MCPClientManager.call_tool() - 直接路由
    3. MCPStdioClient.call_tool() - 通信协议
    4. POST/GET 工具 - 业务实现

    使用示例：
    ```python
    proxy = MCPToolProxy()
    proxy.add_stdio_server("http", uv_path, ["run", "fastmcp", "run", "http_mcp.py:http_mcp"])
    proxy.add_stdio_server("login", uv_path, ["run", "fastmcp", "run", "login_mcp.py:login_mcp"])
    await proxy.initialize()

    # 调用工具
    result = await proxy.call("POST", {"url": "/api/test", "json": {...}})

    # 关闭
    await proxy.close()
    ```
    """

    def __init__(self, name: str = "MCPToolProxy"):
        self.name = name
        self._manager = MCPClientManager()
        self._initialized = False

    def add_http_server(self, name: str, url: str, headers: Dict[str, str] = None) -> "MCPToolProxy":
        """添加HTTP服务器（链式调用）"""
        self._manager.add_http_server(name, url, headers)
        return self

    def add_stdio_server(self, name: str, command: str, args: List[str] = None, env: Dict[str, str] = None) -> "MCPToolProxy":
        """添加stdio服务器（链式调用）"""
        self._manager.add_stdio_server(name, command, args, env)
        return self

    async def initialize(self) -> bool:
        """初始化所有服务器"""
        if self._initialized:
            return True

        results = await self._manager.initialize_all()
        self._initialized = True

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"MCP工具代理初始化完成: {success_count}/{len(results)} 服务器连接成功")
        return success_count > 0

    def list_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具"""
        return self._manager.list_tools()

    async def call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具（统一入口）

        支持两种调用方式：
        1. proxy.call("POST", {...}) - 自动路由
        2. proxy.call("http:POST", {...}) - 显式指定服务器
        """
        # 解析工具名（支持 "server:tool" 格式）
        if ":" in tool_name:
            server_name, actual_tool_name = tool_name.split(":", 1)
            result = await self._manager.call_tool(server_name, actual_tool_name, arguments)
        else:
            # 自动路由
            result = await self._manager.call_tool_by_name(tool_name, arguments)

        # 解析结果
        if result.success:
            inner_data = None
            if result.result:
                try:
                    inner_data = json.loads(result.result)
                except json.JSONDecodeError:
                    inner_data = result.result
            return {"success": True, "result": inner_data, "server": result.server_name}
        else:
            return {"success": False, "error": result.error, "server": result.server_name}

    async def call_server_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用指定服务器的指定工具"""
        result = await self._manager.call_tool(server_name, tool_name, arguments)

        if result.success:
            inner_data = None
            if result.result:
                try:
                    inner_data = json.loads(result.result)
                except json.JSONDecodeError:
                    inner_data = result.result
            return {"success": True, "result": inner_data, "server": server_name}
        else:
            return {"success": False, "error": result.error, "server": server_name}

    def get_servers(self) -> List[str]:
        """获取所有服务器名称"""
        return self._manager.get_servers()

    async def close(self):
        """关闭所有连接"""
        await self._manager.close_all()
        self._initialized = False
