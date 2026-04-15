"""数栈智能体集成测试

测试增强后的 LLMDrivenAgent:
1. MCP工具代理（MCPToolProxy）集成
2. 多MCP服务器支持（HTTP_MCP、Login_MCP等）
3. 记忆模块集成
4. 上下文工程
5. 规划能力
6. 反射机制

用户任务：帮我在62环境创建一个项目，项目名称test_0401_1

注意：本测试会启动MCP服务器的子进程，如果MCP服务器已经在后台运行，请先停止。
"""

import os
import sys
import asyncio
import json

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

from shuzhan_agent.utils.llm_client import MiniMaxLLMClient
from shuzhan_agent.agent.llm_driven_agent import LLMDrivenAgent, Planner
from shuzhan_agent.agent.context_engine import ContextEngine, ContextConfig
from shuzhan_agent.agent.reflector import Reflector
from shuzhan_agent.memory.manager import MemoryManager
from shuzhan_agent.memory.base import MemoryConfig
from shuzhan_agent.mcp import MCPToolProxy, TransportType


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def get_uv_and_paths():
    """获取uv路径和项目路径"""
    uv_path = os.environ.get('UV_PATH', '/usr/local/bin/uv')
    # 测试文件在项目根目录，所以只需要 dirname 一次
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


async def test_mcp_tool_proxy_stdio():
    """测试MCP工具代理 - Stdio模式（子进程启动）"""
    print_section("测试 MCP Tool Proxy (Stdio模式)")

    uv_path, project_root, http_mcp_path, login_mcp_path = get_uv_and_paths()

    proxy = MCPToolProxy()

    # 添加stdio服务器（子进程模式）
    # 命令格式: uv run fastmcp run <script>:<object>
    proxy.add_stdio_server(
        "http",
        uv_path,
        ["run", "fastmcp", "run", f"{http_mcp_path}:http_mcp"]
    )
    proxy.add_stdio_server(
        "login",
        uv_path,
        ["run", "fastmcp", "run", f"{login_mcp_path}:login_mcp"]
    )

    print(f"已注册服务器: {proxy.get_servers()}")
    print(f"uv路径: {uv_path}")

    # 尝试初始化
    try:
        success = await proxy.initialize()
        if success:
            tools = proxy.list_tools()
            print(f"✅ MCP代理初始化成功: {len(tools)} 个工具")
            for tool in tools[:5]:
                print(f"  - {tool['name']}: {tool.get('description', '')[:50]}...")
            if len(tools) > 5:
                print(f"  ... 还有 {len(tools) - 5} 个工具")
        else:
            print("⚠️ MCP代理初始化失败")
    except Exception as e:
        print(f"⚠️ MCP代理初始化异常: {e}")
        import traceback
        traceback.print_exc()

    login_result = await proxy.call("LoginTool", {})

    # 解析返回结果
    if login_result.get("success") and login_result.get("result"):
        inner = login_result["result"]
        print("LoginTool 返回:")
        print(f"  状态: {'成功' if inner.get('success') else '失败'}")
        if inner.get("message"):
            print(f"  消息: {inner['message']}")

        cookie = inner.get("cookie")
        print(f"  Cookie: {cookie if cookie else 'None'}")

        switch_cookie = inner.get("switch_cookie")
        print(f"  Switch Cookie: {switch_cookie if switch_cookie else 'None'}")

        if inner.get("user_info"):
            print(f"  用户信息: {inner['user_info']}")

        if inner.get("environment_name"):
            print(f"  环境: {inner['environment_name']}")

        if inner.get("base_url"):
            print(f"  基础URL: {inner['base_url']}")

    # 打印完整 cookie
    print(f"\n====== 准备发送 POST 请求的 cookie ======")
    print(f"cookie = {cookie}")
    print(f"=============================================\n")

    http_result = await proxy.call("POST", {
      "url": "/api/rdos/common/project/createProject",  # API 路径
      "json": {
          "projectName": "test_0407_6",
          "projectAlias": "test_0407_6",
          "projectEngineList": [{"createModel": 0, "engineType": 1}],
          "isAllowDownload": 1,
          "scheduleStatus": 0,
          "projectOwnerId": "1"
      },
      "cookies": cookie,
      "headers": {
          "Content-Type": "application/json",
          "Accept": "application/json"
      }
    })
    if http_result.get("success"):
        response_data = http_result["result"]
        print(f"响应: {response_data}")


    print("✅ MCP Tool Proxy 配置完成")
    return cookie


def test_context_engine():
    """测试上下文工程"""
    print_section("测试上下文工程")

    config = ContextConfig(max_tokens=8000)
    engine = ContextEngine(config)

    context = engine.build(
        user_query="创建项目",
        conversation_history=[
            {"role": "user", "content": "登录数栈平台"},
            {"role": "assistant", "content": "登录成功"}
        ],
        system_instructions="你是一个数栈平台助手",
        memory_results=[],
        tool_results=[]
    )

    print(f"上下文构建成功，长度: {len(context)}")
    print(f"上下文内容预览:\n{context[:500]}...")

    assert len(context) > 0, "上下文不应为空"
    print("✅ 上下文工程测试通过")


async def test_planner():
    """测试规划器"""
    print_section("测试规划器")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")

    if not api_key:
        print("⚠️ 未配置 API_KEY，跳过规划器测试")
        return

    llm_client = MiniMaxLLMClient(api_key=api_key, base_url=base_url)
    planner = Planner(llm_client)

    tools = await get_available_tools()
    plan = await planner.plan(
        "帮我在62环境创建一个项目，查看创建结果",
        available_tools=tools
    )

    print(f"生成计划 ({len(plan)} 个步骤):")
    for i, step in enumerate(plan[:5], 1):
        if isinstance(step, dict):
            step_text = step.get("step", str(step))
            tool = step.get("tool", "")
            arguments = step.get("arguments", "")
            print(f"  {i}. {step_text}")
            print(f"     tool: {tool}, arguments: {arguments}")
        else:
            print(f"  {i}. {str(step)[:80]}...")
    if len(plan) > 5:
        print(f"  ... 还有 {len(plan) - 5} 个步骤")

    assert len(plan) > 0, "计划不应为空"
    print("✅ 规划器测试通过")


def test_reflector():
    """测试反思器"""
    print_section("测试反思器")

    from shuzhan_agent.agent.reflector import StepResult

    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")

    if not api_key:
        print("⚠️ 未配置 API_KEY，跳过反思器测试")
        return

    llm_client = MiniMaxLLMClient(api_key=api_key, base_url=base_url)
    reflector = Reflector(llm_client)

    async def run_test():
        # 测试成功的步骤
        success_result = StepResult(
            step="登录62环境",
            success=True,
            result="登录成功，获得token"
        )

        reflection = await reflector.reflect("登录62环境", success_result)
        print(f"成功步骤反思: should_retry={reflection.should_retry}, should_replan={reflection.should_replan}")
        print(f"  原因: {reflection.reason}")

        # 测试失败的步骤
        fail_result = StepResult(
            step="创建项目",
            success=False,
            result=None,
            error="HTTP 401: 未授权访问"
        )

        reflection = await reflector.reflect("创建项目", fail_result)
        print(f"\n失败步骤反思: should_retry={reflection.should_retry}, should_replan={reflection.should_replan}")
        print(f"  原因: {reflection.reason}")
        if reflection.suggestions:
            print(f"  建议: {reflection.suggestions}")

    asyncio.run(run_test())
    print("✅ 反思器测试通过")


async def test_full_agent_flow():
    """测试完整Agent流程"""
    print_section("测试完整 Agent 流程")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")

    if not api_key:
        print("⚠️ 未配置 API_KEY，跳过Agent测试")
        return

    llm_client = MiniMaxLLMClient(api_key=api_key, base_url=base_url)

    # 创建MCP代理（Stdio模式 - 子进程启动）
    uv_path, project_root, http_mcp_path, login_mcp_path = get_uv_and_paths()

    proxy = MCPToolProxy()
    proxy.add_stdio_server(
        "http",
        uv_path,
        ["run", "fastmcp", "run", f"{http_mcp_path}:http_mcp"]
    )
    proxy.add_stdio_server(
        "login",
        uv_path,
        ["run", "fastmcp", "run", f"{login_mcp_path}:login_mcp"]
    )

    # 创建Agent
    agent = LLMDrivenAgent(
        llm_client=llm_client,
        name="ShuzhanAgent",
        user_id="test_user",
        enable_planning=True,
        enable_context_engine=True
    )

    # 设置MCP代理
    agent.set_mcp_proxy(proxy)

    # 尝试初始化MCP代理
    try:
        success = await proxy.initialize()
        tools = proxy.list_tools()
        print(f"✅ MCP代理初始化{'成功' if success else '失败'}: {len(tools)} 个工具")
    except Exception as e:
        print(f"⚠️ MCP代理初始化失败（将使用内置工具）: {e}")

    # 打印Agent配置
    print(f"\nAgent配置:")
    print(f"  - 名称: {agent.name}")
    print(f"  - 用户ID: {agent.user_id}")
    print(f"  - 规划能力: {agent.enable_planning}")
    print(f"  - 上下文工程: {agent.context_engine is not None}")
    print(f"  - 反思器: {agent.reflector is not None}")
    print(f"  - 规划器: {agent.planner is not None}")
    print(f"  - MCP代理: {agent._mcp_proxy is not None}")
    login_result = await proxy.call("LoginTool", {})
    login_cookie = login_result['result'].get('cookie')

    # 执行用户任务
    user_task = f"在62环境创建两个项目，添加发布关系"
    print(f"\n📝 用户任务: {user_task}")

    try:
        result = await agent.process(user_task)
        print(f"\n📤 Agent响应:")
        print(f"{result[:1500]}...")
    except Exception as e:
        print(f"❌ Agent执行失败: {e}")
        import traceback
        traceback.print_exc()

    # 检查记忆统计
    stats = agent.memory_manager.get_memory_stats()
    print(f"\n📊 记忆统计:")
    print(f"  - 总记忆数: {stats.get('total_memories', 0)}")
    print(f"  - 记忆类型: {stats.get('memory_types', {})}")

    # 检查对话历史
    print(f"\n💬 对话历史:")
    print(f"  - 对话轮次: {len(agent.conversation_history)}")
    for i, turn in enumerate(agent.conversation_history[-2:], 1):
        print(f"  轮次 {i}: {turn.user_input[:50]}...")

    # 关闭MCP代理
    try:
        await proxy.close()
    except:
        pass

    return agent


def cleanup():
    """清理测试数据"""
    import shutil
    if os.path.exists("./test_memory_data"):
        shutil.rmtree("./test_memory_data")
        print("✅ 测试数据已清理")


if __name__ == "__main__":
    print("="*60)
    print("  数栈智能体集成测试")
    print("="*60)

    try:
        # # 1. 测试MCP工具代理（Stdio模式 - 自己启动子进程）
        # asyncio.run(test_mcp_tool_proxy_stdio())
        #
        # # 2. 测试上下文工程
        # test_context_engine()
        #
        # # 3. 测试凭证存储
        # test_credential_store()
        #
        # # 4. 测试规划器
        # asyncio.run(test_planner())
        #
        # # 5. 测试反思器
        # test_reflector()

        # 6. 测试完整Agent流程
        asyncio.run(test_full_agent_flow())

        print("\n" + "="*60)
        print("  ✅ 所有测试完成")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cleanup()
