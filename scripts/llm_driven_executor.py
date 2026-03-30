#!/usr/bin/env python3
"""
LLM驱动的数栈智能体 - 真正的智能执行

所有MCP能力直接集成到代码中，不依赖外部编辑器：
- BrowserAutomation: Playwright浏览器自动化
- VisionCaptchaSolver: MiniMax视觉API验证码识别
- MiniMaxLLM: LLM驱动
"""

import asyncio
import os
import sys

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
from shuzhan_agent.utils.llm_client import MiniMaxLLMClient
from shuzhan_agent.agent.llm_driven_agent import LLMDrivenAgent
from shuzhan_agent.mcp.playwright_integration import BrowserAutomation


class ShuzhanLLMAgent:
    """
    LLM驱动的数栈智能体

    所有MCP能力直接集成：
    - Playwright: 浏览器自动化登录
    - MiniMax LLM: 智能推理
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

        # 预置的浏览器自动化
        self.browser = None

        print("✅ LLM驱动数栈智能体已初始化")

    async def login(self, url: str = None, username: str = None, password: str = None) -> dict:
        """
        自动化登录数栈平台

        Args:
            url: 登录URL，默认从环境变量获取
            username: 用户名，默认从环境变量获取
            password: 密码，默认从环境变量获取

        Returns:
            登录结果
        """
        url = url or os.getenv("DATASTACK_BASE_URL")
        login_url = url.rstrip("/") + "/login" if url else None
        username = username or os.getenv("DATASTACK_USERNAME")
        password = password or os.getenv("DATASTACK_PASSWORD")

        if not all([login_url, username, password]):
            return {"success": False, "error": "缺少登录信息"}

        print(f"🔐 正在自动化登录...")
        print(f"   URL: {login_url}")
        print(f"   User: {username}")

        # 使用BrowserAutomation登录
        self.browser = BrowserAutomation(headless=False)  # 显示浏览器便于调试
        await self.browser.initialize()

        result = await self.browser.login_datastack(login_url, username, password)

        if result.get("success"):
            cookies = result.get("cookies", {})
            self.agent.set_auth_cookies(cookies)
            print(f"✅ 登录成功!")
            print(f"   获取到 {len(cookies)} 个cookies")
        else:
            print(f"❌ 登录失败: {result}")

        return result

    async def run(self, user_input: str) -> str:
        """
        运行Agent处理用户指令

        Args:
            user_input: 自然语言指令

        Returns:
            Agent的回复
        """
        print(f"\n{'='*60}")
        print(f"👤 用户: {user_input}")
        print(f"{'='*60}\n")

        # Agent处理
        response = await self.agent.process(user_input)

        print(f"\n{'='*60}")
        print(f"🤖 Agent回复:")
        print(response)
        print(f"{'='*60}\n")

        return response

    async def close(self):
        """关闭资源"""
        if self.browser:
            await self.browser.close()


async def main():
    """主函数"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║     LLM驱动的数栈智能体 - 真正的智能执行                    ║
    ║                                                           ║
    ║  特点：                                                    ║
    ║  1. 真正的LLM驱动，不是自动化脚本                        ║
    ║  2. 所有MCP能力直接集成，不依赖外部编辑器                  ║
    ║  3. 浏览器自动化登录，绕过验证码                          ║
    ║  4. MiniMax LLM智能推理                                   ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # 初始化Agent
    agent = ShuzhanLLMAgent()

    # 演示任务
    print("\n📋 演示任务：")
    print("1. 登录数栈平台")
    print("2. 创建项目 test_030_1")
    print("3. 查询项目列表")

    # 1. 先登录
    login_result = await agent.login()
    if not login_result.get("success"):
        print(f"\n⚠️ 登录失败，尝试继续其他操作...")

    # 2. 演示LLM驱动执行
    examples = [
        "帮我在数栈创建一个项目，名称是test_030_1",
        "查看当前有哪些项目",
    ]

    for example in examples:
        await agent.run(example)
        await asyncio.sleep(1)

    # 关闭
    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
