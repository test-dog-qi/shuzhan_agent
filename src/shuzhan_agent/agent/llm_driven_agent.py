"""
真正的LLM驱动Agent

不同于自动化脚本，这个Agent能够：
1. 理解自然语言指令
2. 自主决策使用哪些工具
3. 调用多种MCP完成任务
4. 具有记忆和推理能力
"""

import os
import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from utils.llm_client import MiniMaxLLMClient


@dataclass
class ToolCall:
    """工具调用"""
    name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    success: bool = True


@dataclass
class ConversationTurn:
    """对话回合"""
    user_input: str
    agent_reasoning: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    final_response: str = ""


class LLMDrivenAgent:
    """
    LLM驱动的智能Agent

    核心能力：
    1. 意图理解 - 理解用户的自然语言指令
    2. 工具编排 - 决定使用哪些MCP/工具
    3. 自主执行 - 调用工具并处理结果
    4. 记忆保持 - 记住会话上下文和认证状态
    """

    def __init__(
        self,
        llm_client: MiniMaxLLMClient,
        name: str = "ShuzhanAgent"
    ):
        self.name = name
        self.llm = llm_client
        self.conversation_history: List[ConversationTurn] = []
        self._authenticated = False
        self._auth_cookies: Dict[str, str] = {}
        self._mcp_tools: Dict[str, Any] = {}

        # System prompt - 设定Agent的角色和能力
        self.system_prompt = """你是一个专业的数栈平台智能助手。

你的职责是帮助用户完成数栈平台的各项操作，包括：
- 项目管理（创建、查询、删除项目）
- 数据源管理
- 数据开发（任务创建、调度）
- 运维中心（任务监控、补数等）
- 数据地图

你有以下工具可以使用：
1. playwright - 用于浏览器自动化操作（如登录、获取页面信息）
2. http_request - 用于直接调用API
3. 你的MCP工具列表

工作流程：
1. 理解用户指令
2. 如果需要登录，先用playwright完成登录
3. 规划执行步骤
4. 调用合适的工具
5. 处理结果并反馈

重要原则：
- 如果登录需要验证码，优先使用playwright自动化浏览器登录
- 保持登录状态（cookies），后续请求复用
- 每个操作都要有清晰的进度反馈
"""

    def register_mcp_tool(self, name: str, tool: Any) -> None:
        """注册MCP工具"""
        self._mcp_tools[name] = tool

    async def process(self, user_input: str) -> str:
        """
        处理用户输入

        这是LLM驱动的核心 - Agent使用LLM来：
        1. 理解用户意图
        2. 规划执行步骤
        3. 决定调用哪些工具
        4. 处理结果并生成回复
        """
        # 构建提示
        prompt = self._build_prompt(user_input)

        # 调用LLM
        llm_response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=self._get_available_tools()
        )

        # 处理LLM响应
        content = llm_response.get("content", "")
        tool_calls = llm_response.get("tool_calls", [])

        # 创建对话回合
        turn = ConversationTurn(
            user_input=user_input,
            agent_reasoning=content,
            tool_calls=[]
        )

        # 执行工具调用
        for tool_call in tool_calls:
            result = await self._execute_tool(tool_call)
            turn.tool_calls.append(result)

        # 生成最终回复
        turn.final_response = self._generate_response(turn)
        self.conversation_history.append(turn)

        return turn.final_response

    def _build_prompt(self, user_input: str) -> str:
        """构建提示词"""
        context = ""
        if self._authenticated:
            context += f"\n当前状态：已登录，Cookies: {self._auth_cookies.get('dt_token', '****')[:20]}..."
        else:
            context += "\n当前状态：未登录"

        context += f"\n可用MCP工具: {list(self._mcp_tools.keys())}"

        return f"""{self.system_prompt}

{context}

用户请求: {user_input}

请分析请求，制定执行计划，然后使用工具完成。

如果需要登录，请使用playwright工具自动化完成。
"""

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用的工具列表"""
        tools = []
        for name, tool in self._mcp_tools.items():
            if hasattr(tool, 'get_tools'):
                tools.extend(tool.get_tools())
            elif hasattr(tool, 'name'):
                tools.append({
                    "name": getattr(tool, 'name', name),
                    "description": getattr(tool, 'description', ''),
                })
        return tools

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> ToolCall:
        """执行工具调用"""
        name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})

        try:
            # 查找工具
            tool = self._mcp_tools.get(name)
            if tool:
                if hasattr(tool, 'execute'):
                    result = await tool.execute(**arguments)
                else:
                    result = {"error": f"Tool {name} has no execute method"}
            else:
                result = {"error": f"Tool {name} not found"}

            return ToolCall(
                name=name,
                arguments=arguments,
                result=result,
                success=True
            )
        except Exception as e:
            return ToolCall(
                name=name,
                arguments=arguments,
                result={"error": str(e)},
                success=False
            )

    def _generate_response(self, turn: ConversationTurn) -> str:
        """生成最终回复"""
        lines = [f"**Agent思考**: {turn.agent_reasoning}"]

        if turn.tool_calls:
            lines.append("\n**执行操作**:")
            for tc in turn.tool_calls:
                status = "✅" if tc.success else "❌"
                lines.append(f"  {status} {tc.name}: {tc.result}")

        lines.append(f"\n**最终回复**: {turn.final_response}")

        return "\n".join(lines)

    def set_auth_cookies(self, cookies: Dict[str, str]) -> None:
        """设置认证Cookies"""
        self._auth_cookies = cookies
        self._authenticated = True

    def get_auth_cookies(self) -> Dict[str, str]:
        """获取认证Cookies"""
        return self._auth_cookies

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated
