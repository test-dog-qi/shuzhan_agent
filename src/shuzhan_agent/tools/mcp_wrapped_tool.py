"""
MCP包装工具 - 将MCP服务器中的单个工具包装为独立Tool

当MCPToolWrapper的auto_expand=True时，每个MCP工具都会被包装成MCPWrappedTool
"""

from typing import Dict, Any, List

from .base import Tool, ToolParameter


class MCPWrappedTool(Tool):
    """
    MCP包装工具

    将MCP服务器提供的单个工具包装成独立的Tool对象，
    方便Agent直接调用。
    """

    def __init__(
        self,
        mcp_tool: 'MCPToolWrapper',
        tool_info: Dict[str, Any],
        prefix: str = ""
    ):
        """
        初始化MCP包装工具

        Args:
            mcp_tool: 父级MCPToolWrapper实例
            tool_info: 工具信息字典，包含name、description、input_schema
            prefix: 工具名称前缀
        """
        self._mcp_tool = mcp_tool
        self._tool_info = tool_info
        self.prefix = prefix

        tool_name = tool_info.get('name', 'unknown')
        tool_desc = tool_info.get('description', '')
        input_schema = tool_info.get('input_schema', {})

        # 应用前缀
        self._original_name = tool_name
        self.name = f"{prefix}{tool_name}" if prefix else tool_name
        self.description = tool_desc
        self.input_schema = input_schema

        super().__init__(
            name=self.name,
            description=self.description
        )

    def run(self, parameters: Dict[str, Any]) -> str:
        """
        执行MCP工具调用

        Args:
            parameters: 工具参数

        Returns:
            工具执行结果
        """
        return self._mcp_tool.run({
            "action": "call_tool",
            "tool_name": self._original_name,
            "arguments": parameters
        })

    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        params = []

        # 从input_schema提取参数定义
        schema = self.input_schema
        if isinstance(schema, dict):
            properties = schema.get('properties', {})
            required = schema.get('required', [])

            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')

                params.append(ToolParameter(
                    name=param_name,
                    type=param_type,
                    description=param_desc,
                    required=param_name in required
                ))

        return params

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "description": self.description,
            "original_name": self._original_name,
            "parameters": [param.dict() for param in self.get_parameters()],
            "input_schema": self.input_schema
        }
