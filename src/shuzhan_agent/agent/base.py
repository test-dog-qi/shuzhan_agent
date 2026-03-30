"""Agent基类 - 自研架构，不继承任何现有框架"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import time


class MessageRole(Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """消息结构"""
    role: MessageRole
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_call_id: str
    success: bool
    result: Any
    error: Optional[str] = None


class Tool(ABC):
    """工具基类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """获取工具定义"""
        return {
            "name": self.name,
            "description": self.description,
        }


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [tool.get_schema() for tool in self._tools.values()]


class LLMClient(ABC):
    """LLM客户端抽象"""

    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """聊天接口"""
        pass


class Agent(ABC):
    """
    Agent基类

    设计原则：
    1. 不继承任何外部框架
    2. 核心组件：LLMClient、ToolRegistry、MessageHistory
    3. 支持流式输出和工具调用
    """

    def __init__(
        self,
        name: str,
        llm: LLMClient,
        system_prompt: Optional[str] = None,
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt or ""
        self.tools = ToolRegistry()
        self._history: List[Message] = []
        self._max_iterations = 10
        self._iteration_count = 0

        # 如果有system prompt，添加到历史
        if self.system_prompt:
            self._history.append(Message(
                role=MessageRole.SYSTEM,
                content=self.system_prompt
            ))

    async def run(self, input_text: str, **kwargs) -> str:
        """
        运行Agent处理输入

        子类可以实现自己的run方法，或使用内置的工具调用循环
        """
        self._iteration_count = 0
        self._history.append(Message(
            role=MessageRole.USER,
            content=input_text
        ))

        return await self._run_loop(**kwargs)

    async def _run_loop(self, **kwargs) -> str:
        """内置的工具调用循环"""
        while self._iteration_count < self._max_iterations:
            self._iteration_count += 1

            # 调用LLM
            response = await self.llm.chat(
                messages=self._history,
                tools=self.tools.get_schemas() if self.tools.list_tools() else None,
            )

            # 解析响应
            assistant_message = Message(
                role=MessageRole.ASSISTANT,
                content=response.get("content", ""),
                tool_calls=response.get("tool_calls"),
            )
            self._history.append(assistant_message)

            # 如果没有工具调用，返回结果
            if not assistant_message.tool_calls:
                return assistant_message.content

            # 执行工具调用
            for tool_call in assistant_message.tool_calls:
                result = await self._execute_tool(tool_call)

                # 添加工具结果到历史
                self._history.append(Message(
                    role=MessageRole.TOOL,
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))

        return "达到最大迭代次数"

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> ToolResult:
        """执行单个工具调用"""
        tool_name = tool_call["name"]
        arguments = tool_call.get("arguments", {})

        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(
                tool_call_id=tool_call["id"],
                success=False,
                result=None,
                error=f"Tool '{tool_name}' not found"
            )

        try:
            result = await tool.execute(**arguments)
            return ToolResult(
                tool_call_id=tool_call["id"],
                success=True,
                result=result
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call["id"],
                success=False,
                result=None,
                error=str(e)
            )

    def add_message(self, message: Message) -> None:
        """添加消息到历史"""
        self._history.append(message)

    def clear_history(self) -> None:
        """清空历史"""
        if self.system_prompt:
            self._history = [Message(role=MessageRole.SYSTEM, content=self.system_prompt)]
        else:
            self._history.clear()

    def get_history(self) -> List[Message]:
        """获取历史"""
        return self._history.copy()
