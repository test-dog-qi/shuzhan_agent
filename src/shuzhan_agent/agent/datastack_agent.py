"""数栈智能体工程师 - DataStack Agent"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import Agent, LLMClient, Message, MessageRole, ToolRegistry, ToolResult


# 数栈离线平台系统提示词
DATASTACK_OFFLINE_SYSTEM_PROMPT = """你是一个专注于数栈离线平台的智能体工程师，精通以下模块：

1. **项目管理** - 创建项目、管理成员、角色权限
2. **数据源** - MySQL/PostgreSQL/Hive/Kafka等数据源连接配置
3. **数据开发** - SQL任务、Python任务、Shell任务的创建和调度
4. **运维中心** - 任务监控、周期调度、补数操作、重跑机制
5. **数据地图** - 表管理、血缘关系、权限申请

你的职责：
- 接收用户的自然语言指令（如"帮我在数栈62环境构造主流程测试数据"）
- 理解意图并分解为可执行的步骤
- 调用MCP/Skills完成任务
- 汇报执行进度和结果

执行原则：
1. 先理解需求，再制定计划，最后执行
2. 遇到问题先尝试自主解决，无法解决时报告用户
3. 重要操作前先确认（如删除数据）
4. 保持执行过程透明，让用户了解进度

支持的MCP/Skills：
- datastack_mcp: 数栈平台API调用
- notification_skill: 飞书/钉钉通知
- database_mcp: 数据库直连（如需要）"""


class ExecutionStatus:
    """执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: str
    name: str
    module: str  # project/datasource/data_development/ops_center/data_map
    action: str  # create/update/delete/run/...
    params: Dict[str, Any]
    status: str = ExecutionStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    depends_on: List[str] = []  # 依赖的step_ids


@dataclass
class ExecutionPlan:
    """执行计划"""
    plan_id: str
    description: str
    steps: List[ExecutionStep]
    status: str = ExecutionStatus.PENDING
    results: Dict[str, Any] = {}


@dataclass
class ExecutionReport:
    """执行报告"""
    plan_id: str
    success: bool
    message: str
    steps_executed: int
    steps_failed: int
    duration: float
    details: Dict[str, Any] = {}


@dataclass
class DiagnosisResult:
    """诊断结果"""
    cause: str
    suggestions: List[str]
    can_fix: bool
    fix_action: Optional[str] = None


class DataStackAgent(Agent):
    """
    数栈智能体工程师

    核心能力：
    1. 意图理解 - 解析用户的自然语言指令
    2. 任务分解 - 将需求分解为可执行的步骤
    3. 依赖编排 - 确定步骤间的依赖关系和执行顺序
    4. 自主执行 - 调用MCP/Skills完成任务
    5. 问题诊断 - 识别并尝试修复问题
    """

    def __init__(
        self,
        llm: LLMClient,
        environment: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            name="DataStackAgent",
            llm=llm,
            system_prompt=DATASTACK_OFFLINE_SYSTEM_PROMPT,
        )
        self.environment = environment or {}
        self._execution_context: Dict[str, Any] = {}

    def set_environment(self, env: Dict[str, Any]) -> None:
        """设置环境配置"""
        self.environment = env

    async def execute_plan(self, plan: ExecutionPlan) -> ExecutionReport:
        """
        执行计划

        1. 拓扑排序确定执行顺序
        2. 按批次执行（无依赖的步骤可并行）
        3. 跟踪执行状态
        4. 生成执行报告
        """
        import time
        start_time = time.time()

        # 拓扑排序
        execution_order = self._topological_sort(plan.steps)

        # 分批次执行
        steps_by_batch = self._group_by_batch(plan.steps, execution_order)

        plan.status = ExecutionStatus.RUNNING
        steps_executed = 0
        steps_failed = 0

        for batch in steps_by_batch:
            # 并行执行同批次步骤
            tasks = [self._execute_step(step) for step in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(batch, results):
                if isinstance(result, Exception):
                    step.status = ExecutionStatus.FAILED
                    step.error = str(result)
                    steps_failed += 1
                elif result.success:
                    step.status = ExecutionStatus.SUCCESS
                    step.result = result.result
                    steps_executed += 1
                else:
                    step.status = ExecutionStatus.FAILED
                    step.error = result.error
                    steps_failed += 1

        duration = time.time() - start_time
        plan.status = ExecutionStatus.SUCCESS if steps_failed == 0 else ExecutionStatus.FAILED

        return ExecutionReport(
            plan_id=plan.plan_id,
            success=(steps_failed == 0),
            message="执行完成" if steps_failed == 0 else f"执行失败({steps_failed}个步骤)",
            steps_executed=steps_executed,
            steps_failed=steps_failed,
            duration=duration,
            details={"plan": plan, "context": self._execution_context}
        )

    async def _execute_step(self, step: ExecutionStep) -> ToolResult:
        """执行单个步骤 - 调用对应的MCP"""
        # 这里会调用datastack_mcp
        tool = self.tools.get("datastack_mcp")
        if not tool:
            return ToolResult(
                tool_call_id=step.step_id,
                success=False,
                result=None,
                error="datastack_mcp not found"
            )

        try:
            # 调用MCP
            result = await tool.execute(
                module=step.module,
                action=step.action,
                params=step.params,
                environment=self.environment
            )
            return ToolResult(
                tool_call_id=step.step_id,
                success=True,
                result=result
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=step.step_id,
                success=False,
                result=None,
                error=str(e)
            )

    def _topological_sort(self, steps: List[ExecutionStep]) -> List[str]:
        """拓扑排序确定执行顺序"""
        # 构建依赖图
        graph: Dict[str, List[str]] = {s.step_id: [] for s in steps}
        in_degree: Dict[str, int] = {s.step_id: 0 for s in steps}

        for step in steps:
            for dep in step.depends_on:
                if dep in graph:
                    graph[dep].append(step.step_id)
                    in_degree[step.step_id] += 1

        # Kahn算法
        queue = [sid for sid, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def _group_by_batch(
        self,
        steps: List[ExecutionStep],
        order: List[str]
    ) -> List[List[ExecutionStep]]:
        """按批次分组，无依赖的步骤可并行"""
        step_map = {s.step_id: s for s in steps}
        completed: set = set()
        batches: List[List[ExecutionStep]] = []

        for step_id in order:
            step = step_map[step_id]

            # 检查依赖是否满足
            if all(dep in completed for dep in step.depends_on):
                # 找到同批次的所有可执行步骤
                batch = [
                    step_map[sid] for sid in order
                    if step_map[sid].status == ExecutionStatus.PENDING
                    and all(d in completed for d in step_map[sid].depends_on)
                ]
                if batch and batch not in batches:
                    batches.append(batch)
                    for s in batch:
                        completed.add(s.step_id)

        return batches