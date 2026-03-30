"""
真正的LLM驱动Agent

不同于自动化脚本，这个Agent能够：
1. 理解自然语言指令
2. 自主决策使用哪些工具
3. 调用工具完成任务
4. 具有记忆和推理能力

所有MCP能力直接集成，不依赖外部编辑器
"""

import os
import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from utils.llm_client import MiniMaxLLMClient
from mcp.playwright_integration import BrowserAutomation, VisionCaptchaSolver


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
    agent_reasoning: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    final_response: str = ""


class LLMDrivenAgent:
    """
    LLM驱动的智能Agent

    核心能力：
    1. 意图理解 - 理解用户的自然语言指令
    2. 工具编排 - 决定使用哪些工具
    3. 自主执行 - 调用工具并处理结果
    4. 记忆保持 - 记住会话上下文和认证状态

    内置集成：
    - BrowserAutomation: 浏览器自动化（Playwright）
    - VisionCaptchaSolver: 视觉验证码识别
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
        self._browser: Optional[BrowserAutomation] = None

        # System prompt - 设定Agent的角色和能力
        self.system_prompt = """你是一个专业的数栈平台智能助手。

你有以下内置能力可以直接调用：

1. browser_automation - 浏览器自动化
   - login(url, username, password): 自动化登录
   - navigate(url): 打开网页
   - get_cookies(): 获取当前cookies
   - screenshot(path): 截图

2. vision_solver - 验证码识别
   - solve_captcha(image_path): 识别验证码图片

3. http_request - HTTP请求
   - get/post/put/delete(url, headers, body)

你的工作流程：
1. 理解用户指令
2. 如果需要登录，使用browser_automation自动化登录
3. 使用http_request调用数栈API
4. 返回结果

重要原则：
- 优先使用浏览器自动化完成登录（绕过验证码）
- 登录后保存cookies，后续请求复用
- 每个操作都要有清晰的进度反馈
"""

    async def _get_browser(self) -> BrowserAutomation:
        """获取或创建浏览器实例"""
        if self._browser is None:
            self._browser = BrowserAutomation(headless=True)
            await self._browser.initialize()
        return self._browser

    async def process(self, user_input: str) -> str:
        """
        处理用户输入

        LLM驱动的核心 - Agent使用LLM来：
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
            tools=self._get_tool_definitions()
        )

        # 处理LLM响应
        content = llm_response.get("content", "")
        tool_calls = llm_response.get("tool_calls", [])

        # 创建对话回合
        turn = ConversationTurn(
            user_input=user_input,
            agent_reasoning=content
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
        context = f"\n当前状态："
        if self._authenticated:
            context += f"已登录，Cookies: {list(self._auth_cookies.keys())}"
        else:
            context += "未登录"

        return f"""{self.system_prompt}

{context}

用户请求: {user_input}

请分析请求并决定使用哪些工具。
"""

    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取工具定义"""
        return [
            {
                "name": "browser_login",
                "description": "使用浏览器自动化登录数栈平台，自动处理验证码",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "登录页面URL"},
                        "username": {"type": "string", "description": "用户名"},
                        "password": {"type": "string", "description": "密码"}
                    },
                    "required": ["url", "username", "password"]
                }
            },
            {
                "name": "browser_get_cookies",
                "description": "获取当前浏览器会话的cookies",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "http_request",
                "description": "发送HTTP请求",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                        "url": {"type": "string"},
                        "headers": {"type": "object"},
                        "body": {"type": "object"}
                    },
                    "required": ["method", "url"]
                }
            },
            {
                "name": "solve_image_captcha",
                "description": "识别验证码图片",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string"}
                    },
                    "required": ["image_path"]
                }
            }
        ]

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> ToolCall:
        """执行工具调用"""
        name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})

        try:
            if name == "browser_login":
                result = await self._tool_browser_login(**arguments)
            elif name == "browser_get_cookies":
                result = await self._tool_browser_get_cookies()
            elif name == "http_request":
                result = await self._tool_http_request(**arguments)
            elif name == "solve_image_captcha":
                result = await self._tool_solve_captcha(**arguments)
            else:
                result = {"error": f"Unknown tool: {name}"}

            return ToolCall(
                name=name,
                arguments=arguments,
                result=result,
                success=result.get("error") is None
            )
        except Exception as e:
            return ToolCall(
                name=name,
                arguments=arguments,
                result={"error": str(e)},
                success=False
            )

    async def _tool_browser_login(
        self,
        url: str,
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """浏览器登录工具"""
        browser = await self._get_browser()
        result = await browser.login_datastack(url, username, password)

        if result.get("success"):
            self._auth_cookies = result.get("cookies", {})
            self._authenticated = True

        return result

    async def _tool_browser_get_cookies(self) -> Dict[str, Any]:
        """获取cookies工具"""
        if self._browser:
            cookies = await self._browser.get_cookies()
            return {"cookies": cookies, "authenticated": self._authenticated}
        return {"cookies": {}, "authenticated": False}

    async def _tool_http_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str] = None,
        body: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """HTTP请求工具"""
        import httpx

        # 如果已认证，添加cookies
        if self._authenticated and headers is None:
            headers = {}

        if self._authenticated and self._auth_cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in self._auth_cookies.items()])
            if headers is None:
                headers = {}
            headers["Cookie"] = cookie_str

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body
                )
                return {
                    "status": response.status_code,
                    "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
                }
        except Exception as e:
            return {"error": str(e)}

    async def _tool_solve_captcha(self, image_path: str) -> Dict[str, Any]:
        """验证码识别工具"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")

        solver = VisionCaptchaSolver(api_key=api_key, base_url=base_url)

        try:
            captcha_text = await solver.solve_captcha(image_path)
            return {"captcha": captcha_text}
        except Exception as e:
            return {"error": str(e)}

    def _generate_response(self, turn: ConversationTurn) -> str:
        """生成最终回复"""
        lines = [f"**Agent思考**: {turn.agent_reasoning}"]

        if turn.tool_calls:
            lines.append("\n**执行操作**:")
            for tc in turn.tool_calls:
                status = "✅" if tc.success else "❌"
                lines.append(f"  {status} {tc.name}: {tc.result}")

        lines.append(f"\n**回复**: {turn.final_response}")

        return "\n".join(lines)

    def set_auth_cookies(self, cookies: Dict[str, str]) -> None:
        """设置认证Cookies"""
        self._auth_cookies = cookies
        self._authenticated = True

    def get_auth_cookies(self) -> Dict[str, str]:
        """获取认证Cookies"""
        return self._auth_cookies.copy()

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    async def close(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
