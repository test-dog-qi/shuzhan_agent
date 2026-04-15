"""测试MCP包装器"""

import asyncio
import json
import sys
import os
from datetime import datetime

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

from shuzhan_agent.tools.mcp_wrapper import MCPToolWrapper
from shuzhan_agent.mcp.shuzhan_mcp import mcp


def add_tool(wrapper: MCPToolWrapper):
    """
    自动展开MCP工具

    借鉴simple_agent.py的add_tool方法，将MCP服务器的每个工具
    展开为独立的工具

    Args:
        wrapper: MCPToolWrapper实例

    Returns:
        展开后的工具列表
    """
    if not wrapper.auto_expand:
        return [wrapper]

    expanded_tools = wrapper.get_expanded_tools()
    if expanded_tools:
        print(f"✅ MCP工具 '{wrapper.name}' 已展开为 {len(expanded_tools)} 个独立工具")
        for tool in expanded_tools:
            print(f"   - {tool.name}")
        return expanded_tools

    return [wrapper]


async def test_create_project_flow():
    """测试创建项目完整流程（使用MCPToolProxy + http_mcp + login_mcp）"""
    print("\n" + "=" * 60)
    print("测试创建项目完整流程")
    print("=" * 60)

    from shuzhan_agent.mcp import MCPToolProxy, TransportType

    # 1. 创建MCPToolProxy
    proxy = MCPToolProxy()

    # 获取uv路径
    uv_path = os.environ.get('UV_PATH', '/usr/local/bin/uv')
    project_root = os.path.dirname(os.path.abspath(__file__))
    http_mcp_path = os.path.join(project_root, "src", "shuzhan_agent", "mcp", "http_mcp.py")
    login_mcp_path = os.path.join(project_root, "src", "shuzhan_agent", "mcp", "login_mcp.py")

    # 添加stdio服务器
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

    # 2. 初始化
    print("\n[1] 初始化MCP代理...")
    success = await proxy.initialize()
    print(f"    初始化结果: {success}")
    tools = proxy.list_tools()
    print(f"    可用工具: {[t['name'] for t in tools]}")

    # 3. 登录62环境
    print("\n[2] 登录62环境...")
    username = os.getenv("DATASTACK_USERNAME")
    password = os.getenv("DATASTACK_PASSWORD")

    if not username or not password:
        print(f"    ⚠️ 未配置 DATASTACK_USERNAME 或 DATASTACK_PASSWORD 环境变量")
        print(f"    请在 .env 文件中配置:")
        print(f"    DATASTACK_USERNAME=your_username")
        print(f"    DATASTACK_PASSWORD=your_password")
        return False

    login_result = await proxy.call("LoginTool", {
        "environment_name": "62",
        "username": username,
        "password": password
    })
    print(f"    登录结果: {login_result}")

    # 解析登录结果
    try:
        login_data = json.loads(login_result)
        if not login_data.get("success"):
            print(f"    ❌ 登录失败: {login_data.get('message', 'Unknown error')}")
            return False
        print(f"    ✅ 登录成功")
    except json.JSONDecodeError:
        print(f"    ❌ 登录结果解析失败")
        return False

    # 4. 创建项目
    print("\n[3] 创建项目...")
    project_name = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    create_result = await proxy.call("POST", {
        "url": "/api/projects",
        "json": {"name": project_name, "description": "测试项目"},
        "environment": "62"
    })
    print(f"    创建结果: {create_result}")

    # 5. 验证项目创建
    print("\n[4] 验证项目创建...")
    verify_result = await proxy.call("GET", {
        "url": "/api/projects",
        "params": {"name": project_name},
        "environment": "62"
    })
    print(f"    验证结果: {verify_result}")

    # 6. 关闭
    await proxy.close()

    print("\n" + "=" * 60)
    print(f"测试完成 - 项目名称: {project_name}")
    print("=" * 60)
    return True


def main():
    """主测试函数"""
    print("=" * 60)
    print("MCP包装器测试")
    print("=" * 60)

    # 1. 创建包装器实例
    print("\n[1] 创建包装器...")
    wrapper = MCPToolWrapper(
        name="shuzhan_mcp",
        server_command=["本地"],
        auto_expand=True
    )
    print(f"    名称: {wrapper.name}")
    print(f"    模式: {'本地' if wrapper._is_local else '远程'}")
    print(f"    自动展开: {wrapper.auto_expand}")

    # 2. 设置服务器
    print("\n[2] 设置FastMCP服务器...")
    wrapper.set_server(mcp)
    print(f"    服务器: shuzhan_mcp")

    # 3. 调用run({"action": "list_tools"})
    print("\n[3] 调用 list_tools...")
    result = wrapper.run({"action": "list_tools"})
    print(f"    结果:\n{result}")

    # 4. 使用add_tool展开工具
    print("\n[4] 使用add_tool展开工具...")
    expanded_tools = add_tool(wrapper)

    print("\n[5] 展开的工具详情:")
    for tool in expanded_tools:
        print(f"\n  工具名称: {tool.name}")
        print(f"  描述: {tool.description}")
        print(f"  参数:")
        for param in tool.get_parameters():
            print(f"    - {param.name} ({param.type}): {param.description}")

    print("\n" + "=" * 60)
    print("基础测试完成")
    print("=" * 60)

    # 5. 运行创建项目流程测试
    print("\n是否运行创建项目流程测试? (需要配置 DATASTACK_USERNAME 和 DATASTACK_PASSWORD)")
    response = input("输入 y 运行测试，其他跳过: ").strip().lower()
    if response == 'y':
        asyncio.run(test_create_project_flow())


if __name__ == "__main__":
    main()
