"""
规划层专项测试

聚焦于 Planner 的能力：
1. 任务分解能力
2. 对可用工具的理解
3. 生成可执行计划
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

from shuzhan_agent.utils.llm_client import MiniMaxLLMClient
from shuzhan_agent.agent.llm_driven_agent import Planner
from shuzhan_agent.mcp import MCPToolProxy


def get_uv_and_paths():
    """获取uv路径和项目路径"""
    uv_path = os.environ.get('UV_PATH', '/usr/local/bin/uv')
    project_root = os.path.dirname(os.path.abspath(__file__))
    http_mcp_path = os.path.join(project_root, "src", "shuzhan_agent", "mcp", "http_mcp.py")
    login_mcp_path = os.path.join(project_root, "src", "shuzhan_agent", "mcp", "login_mcp.py")
    return uv_path, project_root, http_mcp_path, login_mcp_path


async def get_available_tools():
    """获取可用的MCP工具"""
    uv_path, project_root, http_mcp_path, login_mcp_path = get_uv_and_paths()

    proxy = MCPToolProxy()
    proxy.add_stdio_server("http", uv_path, ["run", "fastmcp", "run", f"{http_mcp_path}:http_mcp"])
    proxy.add_stdio_server("login", uv_path, ["run", "fastmcp", "run", f"{login_mcp_path}:login_mcp"])

    try:
        await proxy.initialize()
        tools = proxy.list_tools()
        print(f"获取到 {len(tools)} 个工具")
        return tools
    except Exception as e:
        print(f"获取工具失败: {e}")
        return []


async def test_simple_task():
    """测试简单任务分解"""
    print("\n" + "="*60)
    print("  测试1: 简单任务")
    print("="*60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
    llm_client = MiniMaxLLMClient(api_key=api_key, base_url=base_url)
    planner = Planner(llm_client)

    tools = await get_available_tools()

    task = "帮我登录62环境"
    print(f"\n任务: {task}")

    plan = await planner.plan(task, available_tools=tools)

    print(f"\n生成计划 ({len(plan)} 个步骤):")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step}")


async def test_complex_task():
    """测试复杂任务分解"""
    print("\n" + "="*60)
    print("  测试2: 复杂任务")
    print("="*60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
    llm_client = MiniMaxLLMClient(api_key=api_key, base_url=base_url)
    planner = Planner(llm_client)

    tools = await get_available_tools()

    task = "帮我在62环境创建一个项目test_0408_1，查看创建结果"
    print(f"\n任务: {task}")

    plan = await planner.plan(task, available_tools=tools)

    print(f"\n生成计划 ({len(plan)} 个步骤):")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step}")


async def test_multi_step_task():
    """测试多步骤任务"""
    print("\n" + "="*60)
    print("  测试3: 多步骤任务 - 查询并创建")
    print("="*60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
    llm_client = MiniMaxLLMClient(api_key=api_key, base_url=base_url)
    planner = Planner(llm_client)

    tools = await get_available_tools()

    task = "先查询当前有哪些项目，然后创建一个新的项目new_project_0408"
    print(f"\n任务: {task}")

    plan = await planner.plan(task, available_tools=tools)

    print(f"\n生成计划 ({len(plan)} 个步骤):")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step}")


async def main():
    print("="*60)
    print("  规划层专项测试")
    print("  目标：验证 Planner 的任务分解能力")
    print("="*60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ 未配置 API_KEY，请设置 ANTHROPIC_API_KEY 环境变量")
        return

    # 测试1: 简单任务
    await test_simple_task()

    # 测试2: 复杂任务
    await test_complex_task()

    # 测试3: 多步骤任务
    await test_multi_step_task()

    print("\n" + "="*60)
    print("  ✅ 规划层测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())