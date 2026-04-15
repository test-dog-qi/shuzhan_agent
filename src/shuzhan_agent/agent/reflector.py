"""反思器模块 - 基于 AutoGen Reflection 模式

Reflection 模式：LLM生成 → Reflection验证 → 失败时重试/重规划

核心思想：
1. 每个步骤执行后进行反思
2. 验证结果是否符合预期
3. 失败时决定是重试还是重新规划
4. 将反思结果记录到记忆供后续参考
"""

import json
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from shuzhan_agent.utils.llm_client import MiniMaxLLMClient


@dataclass
class StepResult:
    """步骤执行结果"""
    step: str  # 步骤描述
    success: bool  # 是否成功
    result: Any  # 执行结果
    error: Optional[str] = None  # 错误信息（如果有）
    tool_calls: List[Dict] = None  # 工具调用记录

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


@dataclass
class ReflectionResult:
    """反思结果"""
    should_retry: bool = False  # 是否应该重试
    should_replan: bool = False  # 是否应该重新规划
    is_success: bool = True  # 整体是否成功
    reason: str = ""  # 原因说明
    suggestions: List[str] = None  # 改进建议

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


class Reflector:
    """
    反思器 - 验证执行结果，失败时触发重试或重新规划

    基于 AutoGen Reflection 模式设计：
    1. 对每个步骤结果进行反思
    2. 判断是否需要重试（短暂错误）
    3. 判断是否需要重规划（方向错误）
    4. 提供改进建议

    使用示例：
    ```python
    reflector = Reflector(llm_client)

    result = await reflector.reflect(step, step_result)
    if result.should_retry:
        # 重试当前步骤
        ...
    elif result.should_replan:
        # 重新规划
        ...
    ```
    """

    SYSTEM_PROMPT = """你是一个专业的AI执行审查专家。你的任务是审查步骤执行结果并决定最佳后续行动。

审查标准：
1. **成功 (success)**: 步骤完成了预期目标
2. **可重试 (retry)**: 失败是由于暂时性问题（网络、权限等），重试可能成功
3. **需重规划 (replan)**: 失败是由于方向/策略错误，需要重新规划整个任务

判断逻辑：
- 如果步骤成功完成 → success=True
- 如果步骤失败但原因是暂时性的（超时、权限临时不足）→ should_retry=True
- 如果步骤失败且原因是策略性的（API错误、参数错误、逻辑错误）→ should_replan=True

请给出判断结果和改进建议。"""

    def __init__(self, llm_client: MiniMaxLLMClient, max_retries: int = 2):
        """
        初始化反思器

        Args:
            llm_client: LLM客户端
            max_retries: 最大重试次数
        """
        self.llm = llm_client
        self.max_retries = max_retries
        self._retry_count: Dict[str, int] = {}  # 记录每个步骤的重试次数

    async def reflect(self, step: str, result: StepResult) -> ReflectionResult:
        """
        反思步骤执行结果

        Args:
            step: 步骤描述
            result: 步骤执行结果

        Returns:
            反思结果，包含是否重试、是否重规划等决策
        """
        # 快速判断：先检查明显错误模式
        quick_result = self._quick_check(step, result)
        if quick_result:
            return quick_result

        # 深度反思：使用 LLM 分析
        return await self._deep_reflect(step, result)

    def _quick_check(self, step: str, result: StepResult) -> Optional[ReflectionResult]:
        """
        快速检查明显的错误模式

        Returns:
            如果能快速判断，返回 ReflectionResult；否则返回 None
        """
        # 成功情况直接返回
        if result.success:
            return ReflectionResult(
                is_success=True,
                reason="步骤成功完成"
            )

        # 解析错误
        error = result.error or ""
        result_str = str(result.result) if result.result else ""

        # 暂时性错误 → 应该重试
        retry_errors = [
            "timeout", "timed out", "连接超时",
            "network", "网络错误", "网络异常",
            "503", "502", "504",  # 服务不可用
            "429",  # 请求过多
            "permission denied", "权限不足", "临时无权限",
            "rate limit", "频率限制"
        ]

        for pattern in retry_errors:
            if pattern.lower() in error.lower() or pattern.lower() in result_str.lower():
                return ReflectionResult(
                    should_retry=True,
                    is_success=False,
                    reason=f"检测到暂时性错误: {pattern}，建议重试"
                )

        # 策略性错误 → 应该重规划
        replan_errors = [
            "401", "403", "400",  # 认证/授权/参数错误
            "invalid", "错误", "失败",
            "not found", "不存在", "未找到",
            "unauthorized", "未授权",
            "forbidden", "禁止访问"
        ]

        for pattern in replan_errors:
            if pattern.lower() in error.lower() or pattern.lower() in result_str.lower():
                return ReflectionResult(
                    should_replan=True,
                    is_success=False,
                    reason=f"检测到策略性错误: {pattern}，建议重新规划"
                )

        return None

    async def _deep_reflect(self, step: str, result: StepResult) -> ReflectionResult:
        """
        使用 LLM 进行深度反思

        Args:
            step: 步骤描述
            result: 步骤执行结果

        Returns:
            反思结果
        """
        prompt = f"""请审查以下步骤的执行结果：

**步骤**: {step}

**执行结果**:
- 成功: {result.success}
- 结果: {result.result}
- 错误: {result.error or '无'}

**工具调用记录**:
{json.dumps(result.tool_calls, ensure_ascii=False, indent=2) if result.tool_calls else '无'}

请判断：
1. 这个步骤是否成功完成了目标？
2. 如果失败，是因为暂时性问题（应重试）还是策略问题（应重新规划）？
3. 如果需要改进，有什么建议？

请用以下JSON格式回答：
{{
    "is_success": true/false,
    "should_retry": true/false,
    "should_replan": true/false,
    "reason": "判断原因",
    "suggestions": ["建议1", "建议2"]
}}"""

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=self.SYSTEM_PROMPT
            )

            content = response.get("content", "").strip()

            # 尝试从响应中提取 JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ReflectionResult(
                    is_success=data.get("is_success", False),
                    should_retry=data.get("should_retry", False),
                    should_replan=data.get("should_replan", False),
                    reason=data.get("reason", ""),
                    suggestions=data.get("suggestions", [])
                )

            # 如果无法解析，使用保守策略
            return ReflectionResult(
                should_replan=not result.success,
                is_success=result.success,
                reason="无法解析LLM响应，采用保守策略"
            )

        except Exception as e:
            # LLM调用失败时使用保守策略
            return ReflectionResult(
                should_replan=not result.success,
                is_success=result.success,
                reason=f"反思失败: {str(e)[:50]}，采用保守策略"
            )

    def should_continue_retrying(self, step: str) -> bool:
        """
        检查是否应该继续重试

        Args:
            step: 步骤描述

        Returns:
            如果还有重试次数返回 True
        """
        current = self._retry_count.get(step, 0)
        return current < self.max_retries

    def increment_retry(self, step: str) -> None:
        """增加步骤的重试计数"""
        self._retry_count[step] = self._retry_count.get(step, 0) + 1

    def reset_retry(self, step: str) -> None:
        """重置步骤的重试计数（成功时调用）"""
        if step in self._retry_count:
            del self._retry_count[step]

    async def reflect_on_plan(
        self,
        original_task: str,
        plan: List[Dict],
        execution_results: List[StepResult]
    ) -> Dict[str, Any]:
        """
        对整个计划进行反思

        用于计划执行完成后的整体复盘：
        1. 分析哪些步骤成功/失败
        2. 总结执行模式
        3. 为后续任务提供经验

        Args:
            original_task: 原始任务
            plan: 执行计划（每个元素是包含step和reason的字典）
            execution_results: 执行结果列表

        Returns:
            反思总结，包含成功/失败分析和改进建议
        """
        # 格式化计划步骤
        plan_text = "\n".join([
            f"{i+1}. {p.get('step', p) if isinstance(p, dict) else p}"
            for i, p in enumerate(plan)
        ])

        prompt = f"""请对以下任务执行进行整体复盘：

**原始任务**: {original_task}

**执行计划**:
{plan_text}

**执行结果**:
{chr(10).join([
    f"步骤 {i+1}: {'✅ 成功' if r.success else '❌ 失败'} - {r.result or r.error or '无信息'}"
    for i, r in enumerate(execution_results)
])}

请分析：
1. 整体执行情况
2. 成功/失败的关键因素
3. 改进建议

请用以下JSON格式回答：
{{
    "overall_success": true/false,
    "successful_steps": ["步骤描述1", ...],
    "failed_steps": ["步骤描述1", ...],
    "key_factors": ["因素1", ...],
    "improvements": ["改进建议1", ...]
}}"""

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=self.SYSTEM_PROMPT
            )

            content = response.get("content", "").strip()

            # 尝试从响应中提取 JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            return {
                "overall_success": all(r.success for r in execution_results),
                "error": "无法解析LLM响应"
            }

        except Exception as e:
            return {
                "overall_success": all(r.success for r in execution_results),
                "error": str(e)
            }
