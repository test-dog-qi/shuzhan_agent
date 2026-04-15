"""测试脚本 - 使用真实LLM运行ShuzhanAgent"""

import asyncio
import os
from dotenv import load_dotenv

# 确保加载.env文件
load_dotenv()

from shuzhan_agent.agent.llm_driven_agent import LLMDrivenAgent
from shuzhan_agent.utils.llm_client import MiniMaxLLMClient


def create_llm_instance() -> MiniMaxLLMClient:
    """创建LLM实例 - 全局调用点"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")

    return MiniMaxLLMClient(
        api_key=api_key,
        base_url=base_url,
        model="MiniMax-M2.7",
        max_tokens=8192
    )


async def main():
    """主测试函数"""
    print("=" * 60)
    print("ShuzhanAgent 真实LLM测试")
    print("=" * 60)

    # 1. 创建LLM实例
    print("\n[1] 初始化LLM客户端...")
    llm = create_llm_instance()
    print(f"    LLM配置: base_url={llm.base_url}, model={llm.model}")

    # 2. 获取环境配置
    base_url = os.getenv("DATASTACK_BASE_URL", "http://shuzhan62-online-test.k8s.dtstack.cn")
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")
    print(f"\n[2] 环境配置: {base_url}")
    print(f"    用户名: {username}")

    # 3. 创建Agent
    print("\n[3] 创建Agent...")
    agent = LLMDrivenAgent(llm_client=llm, name="ShuzhanAgent")
    print(f"    Agent名称: {agent.name}")

    # 4. 设置认证
    print("\n[4] 设置认证...")
    agent._auth_cookies = {}
    agent._authenticated = False

    # 5. 注册MCP
    print("\n[5] 注册MCP...")
    datastack_mcp = DataStackMCP(
        base_url=base_url,
        api_token=None,
        timeout=30
    )
    print(f"    MCP: DataStackMCP @ {base_url}")

    # 6. 执行测试输入
    test_input = "帮我在62环境中创建一个项目，名称为test_0331_1"

    print("\n" + "=" * 60)
    print(f"用户输入: {test_input}")
    print("=" * 60)

    print("\n[6] Agent处理请求...")

    try:
        # 调用agent处理
        response = await agent.process(test_input)
        print("\n" + "=" * 60)
        print("执行结果:")
        print("=" * 60)
        print(response)

    except Exception as e:
        print("\n" + "=" * 60)
        print("发生错误:")
        print("=" * 60)
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        print("=" * 60)
        # 按要求不直接修改代码，只抛出错误
        raise

    finally:
        # 清理
        print("\n[7] 清理资源...")
        await agent.close()
        print("    浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(main())
