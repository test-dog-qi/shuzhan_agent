"""
MCP工具包装器 - 连接和调用MCP服务器

提供基于FastMCP的MCP工具接口，支持：
- 连接到本地或远程MCP服务器
- 自动展开服务器提供的工具
- 支持社区MCP服务器的扩展
"""

from typing import Dict, Any, List, Optional, Union
import os

from .base import Tool, ToolParameter


class MCPToolWrapper(Tool):
    """
    MCP (Model Context Protocol) 工具包装器

    连接到 MCP 服务器并调用其提供的工具。

    必填参数：
    - name: 工具名称
    - server_command: 服务器启动命令（如 ["python", "server.py"]）
      传参 ["本地"] 时，不进行npx下载，使用内存传输

    可选参数：
    - auto_expand: 是否自动展开为独立工具（默认True）
    - env: 环境变量字典
    """

    def __init__(
        self,
        name: str,
        server_command: List[str],
        auto_expand: bool = True,
        env: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ):
        """
        初始化 MCP 工具包装器

        Args:
            name: 工具名称
            server_command: 服务器启动命令
                - ["本地"] 表示使用内存传输，不进行npx下载
                - ["npx", "-y", "@xxx/server"] 表示使用npx下载
                - ["python", "server.py"] 表示运行本地脚本
            auto_expand: 是否自动展开为独立工具
            env: 环境变量字典
            description: 工具描述（可选）
        """
        self.name = name
        self.server_command = server_command
        self.auto_expand = auto_expand
        self.env = env or {}
        self._client = None
        self._available_tools: List[Dict[str, Any]] = []
        self._server = None
        self.prefix = f"{name}_" if auto_expand else ""

        # 验证server_command
        if not server_command or len(server_command) == 0:
            raise ValueError("server_command 不能为空")

        # 检查是否是本地模式
        self._is_local = server_command == ["本地"] or server_command == ["本地"]

        # 自动发现工具
        if self._is_local and self._server is None:
            # 本地模式，等待外部传入server
            self._available_tools = []
        else:
            self._discover_tools()

        # 设置描述
        if description is None:
            description = self._generate_description()

        super().__init__(
            name=name,
            description=description
        )

    def set_server(self, server: Any) -> None:
        """
        设置FastMCP服务器实例（仅限本地模式）

        Args:
            server: FastMCP服务器实例
        """
        self._server = server
        self._discover_tools()

    def _discover_tools(self) -> None:
        """发现MCP服务器提供的所有工具"""
        try:
            from fastmcp import Client
            import asyncio

            async def discover():
                if self._is_local and self._server:
                    client_source = self._server
                elif isinstance(self.server_command, list) and len(self.server_command) >= 1:
                    client_source = self.server_command
                else:
                    return []

                async with Client(client_source) as client:
                    tools = await client.list_tools()
                    return [
                        {
                            "name": tool.name,
                            "description": tool.description or "",
                            "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                        }
                        for tool in tools
                    ]

            # 运行异步发现
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures

                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(discover())
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    self._available_tools = future.result()
            except RuntimeError:
                self._available_tools = asyncio.run(discover())

        except Exception as e:
            print(f"⚠️ 工具发现失败: {str(e)}")
            self._available_tools = []

    def _generate_description(self) -> str:
        """生成工具描述"""
        if not self._available_tools:
            return f"MCP工具服务器 '{self.name}'，包含{0}个工具。"

        if self.auto_expand:
            return f"MCP工具服务器，包含{len(self._available_tools)}个工具。这些工具会自动展开为独立的工具供Agent使用。"
        else:
            desc_parts = [
                f"MCP工具服务器，提供{len(self._available_tools)}个工具："
            ]
            for tool in self._available_tools:
                tool_name = tool.get('name', 'unknown')
                tool_desc = tool.get('description', '无描述')
                short_desc = tool_desc.split('.')[0] if tool_desc else '无描述'
                desc_parts.append(f"  • {tool_name}: {short_desc}")

            desc_parts.append("\n调用格式：返回JSON格式的参数")
            desc_parts.append('{"action": "call_tool", "tool_name": "工具名", "arguments": {...}}')
            return "\n".join(desc_parts)

    def get_expanded_tools(self) -> List['Tool']:
        """
        获取展开的工具列表

        将MCP服务器的每个工具包装成独立的Tool对象

        Returns:
            Tool对象列表
        """
        if not self.auto_expand:
            return []

        from .mcp_wrapped_tool import MCPWrappedTool

        expanded_tools = []
        for tool_info in self._available_tools:
            wrapped_tool = MCPWrappedTool(
                mcp_tool=self,
                tool_info=tool_info,
                prefix=self.prefix
            )
            expanded_tools.append(wrapped_tool)

        return expanded_tools

    def run(self, parameters: Dict[str, Any]) -> str:
        """
        执行 MCP 操作

        Args:
            parameters: 包含以下参数的字典
                - action: 操作类型 (list_tools, call_tool)
                - tool_name: 工具名称（call_tool 需要）
                - arguments: 工具参数（call_tool 需要）

        Returns:
            操作结果
        """
        from fastmcp import Client

        action = parameters.get("action", "").lower()
        if not action:
            return "错误：必须指定 action 参数"

        try:
            import asyncio

            async def run_mcp_operation():
                if self._is_local and self._server:
                    client_source = self._server
                else:
                    client_source = self.server_command

                async with Client(client_source) as client:
                    if action == "list_tools":
                        tools = await client.list_tools()
                        if not tools:
                            return "没有找到可用的工具"
                        result = f"找到 {len(tools)} 个工具:\n"
                        for tool in tools:
                            result += f"- {tool.name}: {tool.description}\n"
                        return result

                    elif action == "call_tool":
                        tool_name = parameters.get("tool_name")
                        arguments = parameters.get("arguments", {})
                        if not tool_name:
                            return "错误：必须指定 tool_name 参数"
                        result = await client.call_tool(tool_name, arguments)
                        # 解析结果
                        if hasattr(result, 'content') and result.content:
                            if len(result.content) == 1:
                                content = result.content[0]
                                if hasattr(content, 'text'):
                                    return content.text
                                elif hasattr(content, 'data'):
                                    return content.data
                            return str(result)
                        return str(result)

                    else:
                        return f"错误：不支持的操作 '{action}'"

            # 运行异步操作
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures

                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(run_mcp_operation())
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    return future.result()
            except RuntimeError:
                return asyncio.run(run_mcp_operation())

        except Exception as e:
            return f"MCP 操作失败: {str(e)}"

    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="action",
                type="string",
                description="操作类型: list_tools, call_tool",
                required=True
            ),
            ToolParameter(
                name="tool_name",
                type="string",
                description="工具名称（call_tool 操作需要）",
                required=False
            ),
            ToolParameter(
                name="arguments",
                type="object",
                description="工具参数（call_tool 操作需要）",
                required=False
            ),
        ]

    def list_tools(self) -> List[Dict[str, Any]]:
        """获取发现的工具列表"""
        return self._available_tools
