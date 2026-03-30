#!/usr/bin/env python3
"""
LLM驱动的数栈智能体 - 真正的智能执行

不同于自动化脚本，这个Agent：
1. 理解自然语言指令
2. 使用LLM规划执行步骤
3. 调用MCP/工具完成任务
4. 具有记忆和推理能力
"""

import asyncio
import os
import sys

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
from utils.llm_client import MiniMaxLLMClient
from agent.llm_driven_agent import LLMDrivenAgent
from mcp.datastack_mcp import DataStackMCP
from mcp.playwright_mcp import PlaywrightMCPTool


class ShuzhanLLMAgent:
    """
    LLM驱动的数栈智能体

    集成多种MCP能力：
    - Playwright: 自动化登录（绕过验证码）
    - DataStack: 数栈API调用
    - HTTP: 通用HTTP请求
    """

    def __init__(self):
        load_dotenv()

        # 初始化LLM
        self.llm = MiniMaxLLMClient(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
        )

        # 初始化Agent
        self.agent = LLMDrivenAgent(
            llm_client=self.llm,
            name="ShuzhanLLMAgent"
        )

        # 注册MCP工具
        self._register_mcp_tools()

    def _register_mcp_tools(self):
        """注册所有MCP工具"""

        # 数栈API MCP
        datastack_mcp = DataStackMCP(
            base_url=os.getenv("DATASTACK_BASE_URL", "http://localhost:8080"),
            timeout=30
        )
        self.agent.register_mcp_tool("datastack", datastack_mcp)

        # Playwright MCP（用于登录）
        playwright_tool = PlaywrightMCPTool()
        self.agent.register_mcp_tool("playwright", playwright_tool)

        # HTTP请求工具（备用）
        self.agent.register_mcp_tool("http", HttpTool())

    async def run(self, user_input: str) -> str:
        """
        运行Agent处理用户指令

        Args:
            user_input: 自然语言指令，如"帮我在数栈创建项目test_030_1"

        Returns:
            Agent的回复
        """
        print(f"\n{'='*60}")
        print(f"用户: {user_input}")
        print(f"{'='*60}\n")

        # Agent处理
        response = await self.agent.process(user_input)

        print(f"\n{'='*60}")
        print(f"Agent回复:")
        print(response)
        print(f"{'='*60}\n")

        return response

    def set_auth_cookies(self, cookies: dict):
        """设置认证cookies"""
        self.agent.set_auth_cookies(cookies)


class HttpTool:
    """简单的HTTP请求工具"""

    def __init__(self):
        self.name = "http_request"
        self.description = "发送HTTP请求"

    def get_tools(self) -> list:
        return [{
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
        }]

    async def execute(self, method: str, url: str, headers: dict = None, body: dict = None, **kwargs) -> dict:
        """执行HTTP请求"""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
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


async def main():
    """主函数"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║        LLM驱动的数栈智能体 - 智能执行                    ║
    ║                                                           ║
    ║  不同于自动化脚本，这是一个真正的智能Agent：              ║
    ║  1. 理解自然语言指令                                     ║
    ║  2. LLM规划执行步骤                                      ║
    ║  3. 调用MCP完成各种操作                                  ║
    ║  4. 具有记忆和推理能力                                   ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # 初始化Agent
    agent = ShuzhanLLMAgent()

    # 演示对话
    examples = [
        "帮我在数栈创建一个项目，名称是test_030_1",
        "查看当前有哪些项目",
        "帮我登录数栈平台，用户名是admin@dtstack.com"
    ]

    for example in examples:
        await agent.run(example)
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
