"""数栈智能体工程师 - 主入口"""

import asyncio
import os
from dotenv import load_dotenv
from typing import Optional

from agent.datastack_agent import DataStackAgent, ExecutionPlan, ExecutionStep
from agent.mixins.offline_expert import OfflineExpertMixin
from agent.mixins.troubleshooter import TroubleshooterMixin
from mcp.datastack_mcp import DataStackMCP
from mcp.auth import DataStackAuth
from skills.notification import NotificationSkill
from config.offline_flows import MAIN_FLOW_REGRESSION, ENVIRONMENT_TEMPLATE
from config.environments import EnvironmentRouter, PREDEFINED_ENVIRONMENTS


class ShuzhanAgent(
    DataStackAgent,
    OfflineExpertMixin,
    TroubleshooterMixin
):
    """
    数栈智能体工程师

    整合了：
    - DataStackAgent: Agent核心能力
    - OfflineExpertMixin: 离线平台专家知识
    - TroubleshooterMixin: 问题排查能力
    - EnvironmentRouter: 环境智能路由
    """

    def __init__(
        self,
        llm,
        environment: Optional[dict] = None,
        notification_channel: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        super().__init__(llm=llm, environment=environment)

        # 初始化环境路由
        self.env_router = EnvironmentRouter()

        # 认证信息
        self.username = username or os.getenv("DATASTACK_USERNAME")
        self.password = password or os.getenv("DATASTACK_PASSWORD")

        # 注册MCP
        self._setup_mcp()

        # 设置认证
        self._setup_auth()

        # 设置通知
        self._setup_notification(notification_channel)

    def _setup_mcp(self):
        """设置MCP"""
        env = self.environment or {}
        datastack_mcp = DataStackMCP(
            base_url=env.get("base_url", "http://localhost:8080"),
            api_token=env.get("api_token"),
            timeout=env.get("timeout", 30)
        )
        self.tools.register(datastack_mcp)

    def _setup_auth(self):
        """设置认证"""
        env = self.environment or {}
        if self.username and self.password:
            base_url = env.get("base_url", "")
            self.auth = DataStackAuth(
                base_url=base_url,
                username=self.username,
                password=self.password
            )
        else:
            self.auth = None

    def _setup_notification(self, channel_name: Optional[str] = None):
        """设置通知渠道"""
        self.notification = NotificationSkill()

        if channel_name:
            # 从环境变量读取webhook
            webhook = os.getenv(f"{channel_name.upper()}_WEBHOOK")
            if webhook:
                self.notification.add_channel(
                    name=channel_name,
                    channel_type="feishu",  # 或 "dingtalk"
                    webhook_url=webhook
                )

    def route_environment(self, user_input: str) -> Optional[dict]:
        """
        根据用户自然语言智能路由环境

        Args:
            user_input: 用户输入，如"帮我看62环境的任务"

        Returns:
            匹配的环境配置
        """
        matched_env = self.env_router.route(user_input)
        if matched_env:
            return {
                "name": matched_env.name,
                "version": matched_env.version,
                "base_url": matched_env.base_url,
                "description": matched_env.description,
                "matched_score": "高"  # 实际可返回具体分数
            }
        return None

    def list_environments(self) -> list:
        """列出所有可用环境"""
        return [
            {
                "name": e.name,
                "version": e.version,
                "base_url": e.base_url,
                "tags": e.tags
            }
            for e in self.env_router.get_all_environments()
        ]

    def add_custom_environment(self, env_config: dict) -> None:
        """添加自定义环境"""
        from config.environments import DataStackEnvironment
        env = DataStackEnvironment(
            name=env_config["name"],
            version=env_config["version"],
            base_url=env_config["base_url"],
            description=env_config.get("description", ""),
            tags=env_config.get("tags", [])
        )
        self.env_router.add_environment(env)

    async def execute_main_flow(
        self,
        env_name: str = "offline_62",
        notify: bool = True
    ) -> dict:
        """
        执行主流程回归测试

        Args:
            env_name: 环境名称
            notify: 是否发送通知

        Returns:
            执行结果
        """
        # 获取环境配置
        env_config = ENVIRONMENT_TEMPLATE.get(env_name, {})
        self.set_environment(env_config)

        # 通知开始
        if notify:
            await self.notification.send_message(
                "default",
                f"🚀 开始执行主流程回归测试\n环境: {env_config.get('name', env_name)}"
            )

        # 生成执行计划
        intent = self.understand_intent("主流程回归测试")
        plan_steps = self.generate_execution_plan(intent)

        # 转换为ExecutionStep
        steps = []
        for i, step_config in enumerate(MAIN_FLOW_REGRESSION):
            step = ExecutionStep(
                step_id=step_config["step_id"],
                name=step_config["name"],
                module=step_config["module"],
                action=step_config["action"],
                params=step_config.get("required_params", {}),
                depends_on=step_config.get("depends_on", [])
            )
            steps.append(step)

        # 创建执行计划
        plan = ExecutionPlan(
            plan_id=f"main_flow_{env_name}_{int(asyncio.get_event_loop().time())}",
            description=f"主流程回归测试 - {env_config.get('name', env_name)}",
            steps=steps
        )

        # 执行计划
        report = await self.execute_plan(plan)

        # 发送执行报告
        if notify:
            await self.notification.send_report("default", {
                "plan_id": report.plan_id,
                "success": report.success,
                "message": report.message,
                "steps_executed": report.steps_executed,
                "steps_failed": report.steps_failed,
                "duration": report.duration
            })

        return {
            "success": report.success,
            "report": report
        }


async def main():
    """主函数"""
    # 加载环境变量
    load_dotenv()

    # 简单的LLM客户端实现（实际应该接入真实的LLM）
    class SimpleLLMClient:
        async def chat(self, messages, tools=None, **kwargs):
            # 这里应该调用真实的LLM API
            return {
                "content": "收到指令，正在分析...",
                "tool_calls": None
            }

    # 创建Agent
    agent = ShuzhanAgent(
        llm=SimpleLLMClient(),
        username=os.getenv("DATASTACK_USERNAME", "admin@dtstack.com"),
        password=os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")
    )

    # 演示环境路由功能
    print("=== 环境路由演示 ===")
    print(f"可用环境: {agent.list_environments()}")

    # 测试路由
    test_inputs = [
        "帮我看62测试环境",
        "在63预发环境造数",
        "离线62版本的任务"
    ]
    for inp in test_inputs:
        matched = agent.route_environment(inp)
        print(f"输入: '{inp}' => 路由结果: {matched}")

    # 执行主流程
    result = await agent.execute_main_flow(env_name="offline_62")

    print(f"执行结果: {result}")


if __name__ == "__main__":
    asyncio.run(main())
