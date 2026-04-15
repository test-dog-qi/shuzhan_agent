"""
真正的LLM驱动Agent

不同于自动化脚本，这个Agent能够：
1. 理解自然语言指令
2. 自主决策使用哪些工具
3. 调用工具完成任务
4. 具有记忆和推理能力
5. 自动规划复杂任务

所有MCP能力直接集成，不依赖外部编辑器
"""

import os
import json
import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from shuzhan_agent.utils.llm_client import MiniMaxLLMClient
from shuzhan_agent.mcp.playwright_integration import BrowserAutomation
from shuzhan_agent.mcp.api_reference import format_api_for_llm, get_all_apis
from shuzhan_agent.memory.manager import MemoryManager
from shuzhan_agent.memory.base import MemoryConfig
from shuzhan_agent.agent.context_engine import ContextEngine, ContextConfig
from shuzhan_agent.agent.reflector import Reflector, StepResult, ReflectionResult


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
    plan: List[Dict] = field(default_factory=list)  # [{"step": str, "reason": str}, ...]


class Planner:
    """规划器 - 使用LLM分解复杂任务为业务操作步骤"""

    # LLM自行判断是否需要规划的Prompt
    SHOULD_PLAN_PROMPT = """你是一个顶级的AI规划专家。你的任务是根据用户问题判断是否需要进行复杂的任务规划。

判断标准：
- 需要多步骤完成= 需要规划
- 单一操作= 不需要规划

问题: {question}

请只回答"是"或"否"，不要解释。"""

    # 生成执行计划的Prompt
    PLAN_PROMPT = """你是一个顶级的AI规划专家。你的任务是将用户提出的复杂问题分解成一个由多个简单步骤组成的行动计划。

请确保计划中的每个步骤都是一个独立的、可执行的子任务，并且严格按照逻辑顺序排列。

请严格按照逻辑顺序规划步骤，不要规划登录步骤，登录会在后续进行处理"""

    def __init__(self, llm_client: MiniMaxLLMClient):
        self.llm_client = llm_client

    async def should_plan(self, user_input: str) -> bool:
        """使用LLM自行判断是否为复杂任务"""
        prompt = self.SHOULD_PLAN_PROMPT.format(question=user_input)
        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.llm_client.chat(messages=messages)
            content = (response.get("content") or "").strip().lower()
            return "是" in content or "yes" in content or "true" in content
        except Exception as e:
            print(f"LLM规划判断失败: {e}")
            return True

    async def plan(self, user_input: str, available_tools: List[Dict] = None) -> List[Dict]:
        """
        生成执行计划

        Args:
            user_input: 用户输入
            available_tools: 可用工具列表（用于提供上下文）

        Returns:
            步骤列表，每个步骤包含 step 和 reason 字段
            如果生成失败，返回带警告的单个步骤列表
        """
        tools = available_tools or []

        # 构建工具上下文（只包含name和description）
        tools_list = ""
        if tools:
            tools_list = "\n".join([f"- {t.get('name', 'unknown')}: {t.get('description', '无描述')}" for t in tools])

        # 获取API参考文档（只包含name和description）
        api_reference = format_api_for_llm()
        api_str = "\n".join([f"- {k}: {v}" for k, v in api_reference.items()])
        valid_api_keys = list(api_reference.keys())

        # JSON格式说明
        json_format_example = '''请严格按照以下JSON格式输出计划,```python与```作为前后缀是必要的:
```python
[
  {"step": "步骤描述", "tool": "工具名", "arguments": "API_key"},
  {"step": "步骤描述", "tool": "工具名", "arguments": "API_key"}
]
```

【可用工具】（根据description决定使用哪个tool）
''' + tools_list + '''

【数栈平台功能列表】（根据description做计划分解，arguments必须使用这里的key）
''' + api_str + '''

【强制要求】
- 不要规划登录步骤，登录会在后续进行处理
- arguments字段只能使用【数栈平台功能列表】中的key，禁止使用其他值
- 可用API key列表：''' + str(valid_api_keys) + '''
- 如果某步骤不需要调用API，arguments必须为空字符串''
- 禁止在arguments中填写具体参数值，只能填写API key
- 只输出计划，不要其他内容。'''

        user_content = f"问题: {user_input}\n\n请生成执行计划。\n\n{json_format_example}"

        messages = [
            {"role": "user", "content": user_content}
        ]

        try:
            response = await self.llm_client.chat(
                messages=messages,
                system_prompt=self.PLAN_PROMPT
            )

            content = (response.get("content") or "").strip()
            if content:
                steps = self._parse_plan_from_json(content)
                if steps:
                    print(f"✅ 从JSON解析到 {len(steps)} 个步骤")
                    return steps

            print(f"⚠️ 无法生成有效计划，LLM返回内容为空")
            return [{"step": f"[警告: 规划失败] {user_input}", "reason": "无法生成有效计划"}]

        except Exception as e:
            error_msg = str(e)
            print(f"❌ 生成计划失败: {error_msg}")
            return [{"step": f"[错误: {error_msg[:50]}] {user_input}", "reason": str(e)}]

    def _parse_plan_from_json(self, text: str) -> List[Dict]:
        """从LLM返回的JSON文本中解析计划步骤

        支持两种格式：
        1. 新格式（推荐）：{"step": "步骤描述", "tool": "POST", "arguments": "API_key", "reason": "..."}
        2. 旧格式（兼容）：{"step": "步骤描述", "reason": "..."}
        """
        import re
        import json

        # 尝试直接解析JSON
        # 去除可能存在的markdown代码块标记
        text_cleaned = text.strip()
        if text_cleaned.startswith("```"):
            # 去除 ```json 或 ``` 标记
            lines = text_cleaned.split('\n')
            lines = [l for l in lines if not l.startswith("```") and not l.startswith("json")]
            text_cleaned = '\n'.join(lines).strip()

        # 尝试找JSON数组
        json_match = re.search(r'\[.*\]', text_cleaned, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, list) and len(parsed) > 0:
                    # 验证结构 - 新格式优先
                    valid_steps = []
                    for item in parsed:
                        if isinstance(item, dict):
                            # 新格式：{"tool": "POST", "arguments": {...}, "reason": "..."}
                            if "tool" in item and "arguments" in item:
                                valid_steps.append({
                                    "step": item["step"],
                                    "tool": item["tool"],
                                    "arguments": item["arguments"]
                                })
                            # 旧格式兼容：{"step": "描述", "reason": "..."}
                            elif "step" in item:
                                valid_steps.append({
                                    "step": item["step"],
                                    "reason": item.get("reason", "")
                                })
                    if valid_steps:
                        return valid_steps
            except json.JSONDecodeError:
                pass

        # 回退：尝试从文本中提取结构化信息
        print(f"⚠️ JSON解析失败，尝试文本解析")
        lines = text.split('\n')
        steps = []
        current_step = {}
        for line in lines:
            line = line.strip()
            # 匹配 "tool": "POST" 或 "step": "xxx" 格式
            tool_match = re.search(r'["\']tool["\']\s*:\s*["\'](.+?)["\']', line, re.IGNORECASE)
            step_match = re.search(r'["\']step["\']\s*:\s*["\'](.+?)["\']', line, re.IGNORECASE)
            reason_match = re.search(r'["\']reason["\']\s*:\s*["\'](.+?)["\']', line, re.IGNORECASE)
            if tool_match:
                current_step["tool"] = tool_match.group(1)
            elif step_match:
                current_step["step"] = step_match.group(1)
            if reason_match:
                current_step["reason"] = reason_match.group(1)
                if current_step:
                    steps.append(current_step)
                    current_step = {}
        return steps


class Executor:
    """执行器 - 严格按照计划一步步执行"""

    EXECUTE_PROMPT = """你是一位顶级的AI执行专家。你的任务是严格按照给定的计划，一步步地解决问题。
你将收到原始问题、完整的计划、以及到目前为止已经完成的步骤和结果。
请你专注于解决"当前步骤"，并仅输出该步骤的最终答案，不要输出任何额外的解释或对话。

# 原始问题:
{question}

# 完整计划:
{plan}

# 历史步骤与结果:
{history}

# 当前步骤:
{current_step}

请仅输出针对"当前步骤"的回答，如果执行失败请明确说明失败原因。"""

    def __init__(self, llm_client: MiniMaxLLMClient):
        self.llm_client = llm_client

    async def execute_step(
        self,
        question: str,
        plan: List[Dict],
        history: List[str],
        current_step: Dict
    ) -> str:
        """
        执行单个步骤

        Args:
            question: 原始问题
            plan: 完整计划
            history: 历史步骤结果
            current_step: 当前步骤

        Returns:
            执行结果（成功或失败原因）
        """
        # 格式化历史
        history_text = "\n".join([
            f"步骤{i+1}: {h}"
            for i, h in enumerate(history)
        ]) if history else "无"

        # 格式化计划
        plan_text = "\n".join([
            f"{i+1}. {p.get('step', p)}" + (f" [工具: {p.get('tool', '')}]" if isinstance(p, dict) and p.get('tool') else "")
            for i, p in enumerate(plan)
        ])

        prompt = self.EXECUTE_PROMPT.format(
            question=question,
            plan=plan_text,
            history=history_text,
            current_step=current_step.get("step", str(current_step))
        )

        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.llm_client.chat(messages=messages)
            content = response.get("content", "")
            return content.strip()
        except Exception as e:
            return f"执行失败: {str(e)}"


class LLMDrivenAgent:
    """
    LLM驱动的智能Agent

    核心能力：
    1. 意图理解 - 理解用户的自然语言指令
    2. 工具编排 - 决定使用哪些工具
    3. 自主执行 - 调用工具并处理结果
    4. 记忆保持 - 记住会话上下文和认证状态
    5. 自动规划 - 分解复杂任务为简单步骤

    内置集成：
    - MemoryManager: 记忆管理
    - ContextEngine: 上下文工程
    - MCPToolWrapper: MCP工具包装器（可选项）
    """

    def __init__(
        self,
        llm_client: MiniMaxLLMClient,
        name: str = "ShuzhanAgent",
        user_id: str = "default_user",
        memory_config: MemoryConfig = None,
        enable_planning: bool = True,
        enable_context_engine: bool = True,
        mcp_wrapper: Any = None
    ):
        self.name = name
        self.llm = llm_client
        self.user_id = user_id
        self.enable_planning = enable_planning
        self.conversation_history: List[ConversationTurn] = []
        self._authenticated = False
        self._auth_cookies: Dict[str, str] = {}
        self._browser: Optional[BrowserAutomation] = None
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self._base_url: Optional[str] = None

        # MCP工具包装器（保留兼容，支持旧的mcp_wrapper参数）
        self._mcp_wrapper = mcp_wrapper

        # 新的MCP工具代理（统一网关模式）
        self._mcp_proxy = None

        # 初始化记忆模块
        self.memory_config = memory_config or MemoryConfig()
        self.memory_manager = MemoryManager(
            config=self.memory_config,
            user_id=user_id,
            enable_working=True,
            enable_episodic=True
        )

        # 初始化上下文工程
        self.context_engine = ContextEngine(
            config=ContextConfig(max_tokens=8000)
        ) if enable_context_engine else None

        # 初始化规划器
        self.planner = Planner(llm_client) if enable_planning else None

        # 初始化反思器
        self.reflector = Reflector(llm_client) if enable_planning else None

        # System prompt - 设定Agent的角色和能力
        self.system_prompt = """你是一个专业的数栈平台智能助手。

你有以下MCP可以直接调用：

1. login_mcp - API登录（推荐）
   - login(environment_name, username, password, base_url): API登录数栈
   - 支持多环境：62、63、生产等

2. http_mcp - HTTP请求
   - get/post/put/delete(url, body): 发送HTTP请求

你的工作流程：
1. 理解用户指令
2. 如果用户提到具体环境（如"62环境"、"63环境"），使用对应的登录URL
3. 如果用户没有指定环境但任务需要登录，询问用户要登录哪个环境
4. 优先使用 LoginTool 进行API登录（更优雅）
5. 使用http_mcp调用数栈API
6. 返回结果

重要原则：
- 多环境支持：通过 environment_name 参数指定环境
- 复杂任务使用规划能力分解步骤"""

    def set_mcp_proxy(self, proxy: 'MCPToolProxy') -> None:
        """
        设置MCP工具代理（统一网关模式）

        Args:
            proxy: MCPToolProxy实例

        使用示例：
        ```python
        from shuzhan_agent.mcp import MCPToolProxy, create_mcp_gateway

        proxy = MCPToolProxy()
        proxy.add_http_server("http", "http://localhost:8080/mcp")
        proxy.add_http_server("login", "http://localhost:8081/mcp")

        agent = LLMDrivenAgent(llm_client)
        agent.set_mcp_proxy(proxy)
        ```
        """
        self._mcp_proxy = proxy
        return True

    async def _get_browser(self) -> BrowserAutomation:
        """获取或创建浏览器实例"""
        if self._browser is None:
            self._browser = BrowserAutomation(headless=True)
            await self._browser.initialize()
        return self._browser

    async def _should_plan(self, user_input: str) -> bool:
        """
        使用LLM判断是否为复杂任务（需要规划）

        主流方案：让LLM直接判断任务复杂度，决定是否需要规划
        优点：准确率高，可处理未知任务，主流框架（LangChain、AutoGen）常用
        """
        # 简单任务快速判断（无需LLM）
        simple_keywords = ["天气", "时间", "你好", "hello", "hi", "请问现在"]
        if any(kw in user_input.lower() for kw in simple_keywords):
            return False

        # 使用LLM判断
        try:
            planning_prompt = f"""判断以下任务是否需要多步骤规划来执行。

任务：{user_input}

判断标准：
- 需要多步骤完成（例如：登录→查询→操作→验证）= 需要规划
- 单一工具调用（例如：如查天气、问时间）= 不需要规划
- 包含"创建"、"批量"、"首先然后最后"、"多个"等= 需要规划

请只回答"是"或"否"，不要解释。"""

            messages = [{"role": "user", "content": planning_prompt}]
            response = await self.llm.chat(messages=messages)
            response_text = (response.get("content") or "").strip().lower()

            # 解析响应
            if "是" in response_text or "yes" in response_text:
                return True
            elif "否" in response_text or "no" in response_text:
                return False

            # 默认返回True（倾向于规划）
            return True

        except Exception as e:
            print(f"LLM规划判断失败: {e}")
            # 失败时使用简单的关键字判断作为fallback
            complex_keywords = ["创建", "多个", "首先", "然后", "最后", "批量", "自动化", "流程"]
            return any(kw in user_input for kw in complex_keywords)

    async def process(self, user_input: str) -> str:
        """
        处理用户输入

        LLM驱动的核心 - Agent使用LLM来：
        1. 理解用户意图
        2. 规划执行步骤（复杂任务）
        3. 决定调用哪些工具
        4. 处理结果并生成回复
        """
        # 1. 从记忆检索相关上下文
        memory_results = []
        if self.context_engine:
            try:
                memory_results = self.memory_manager.retrieve_memories(
                    query=user_input,
                    limit=3
                )
            except Exception as e:
                print(f"记忆检索失败: {e}")

        # 3. 构建结构化上下文
        if self.context_engine:
            conversation_dicts = [
                {"role": "user", "content": t.user_input}
                for t in self.conversation_history[-5:]
            ]
            structured_context = self.context_engine.build(
                user_query=user_input,
                conversation_history=conversation_dicts,
                system_instructions=self.system_prompt,
                memory_results=memory_results
            )
        else:
            structured_context = self._build_prompt(user_input)

        # 4. 判断是否需要规划（使用LLM自判断）
        plan = None
        if self.planner and await self._should_plan(user_input):
            plan = await self.planner.plan(
                user_input,
                available_tools=self._get_tool_definitions()
            )
            if plan:
                print(f"生成计划: {plan}")

        # 5. 执行（规划模式或直接模式）
        if plan:
            result = await self._execute_with_plan(plan, user_input, structured_context)
        else:
            result = await self._execute_direct(user_input, structured_context)

        # 6. 记录到工作记忆
        self._record_to_memory(user_input, result)

        return result

    async def _execute_direct(self, user_input: str, context: str) -> str:
        """直接执行模式（简单任务）"""
        messages = [{"role": "user", "content": context}]

        llm_response = await self.llm.chat(
            messages=messages,
            tools=self._get_tool_definitions()
        )

        content = llm_response.get("content", "")
        tool_calls = llm_response.get("tool_calls", [])

        turn = ConversationTurn(
            user_input=user_input,
            agent_reasoning=content
        )

        for tool_call in tool_calls:
            result = await self._execute_tool(tool_call)
            turn.tool_calls.append(result)

        turn.final_response = self._generate_response(turn)
        self.conversation_history.append(turn)

        return turn.final_response

    async def _execute_with_plan(self, plan: List[Dict], user_input: str, context: str) -> str:
        """规划执行模式（复杂任务）- 带反思机制"""
        results = []
        step_results = []  # 存储 StepResult 供反思用
        turn = ConversationTurn(
            user_input=user_input,
            plan=plan
        )

        print(f"\n开始执行计划（共 {len(plan)} 步）:")
        login_result = await self._mcp_proxy.call("LoginTool", {})
        cookie = login_result["result"].get("cookie")

        for i, step_dict in enumerate(plan, 1):
            # 支持两种格式：
            # 1. 新格式：{"tool": "POST", "arguments": {...}, "reason": "..."}
            # 2. 旧格式：{"step": "描述", "reason": "..."}
            step_tool = step_dict.get("tool", "") if isinstance(step_dict, dict) else ""
            step_arguments = step_dict.get("arguments", "") if isinstance(step_dict, dict) else {}
            step_text = step_dict.get("step", step_tool) if isinstance(step_dict, dict) else str(step_dict)
            step_reason = step_dict.get("reason", "") if isinstance(step_dict, dict) else ""

            # 跳过警告标记的步骤
            if step_text.startswith("[警告") or step_text.startswith("[错误"):
                print(f"\n-> 跳过步骤 {i}: {step_text}")
                results.append(f"[跳过] {step_text}")
                step_results.append(StepResult(step=step_text, success=False, result="步骤被跳过"))
                continue

            print(f"\n-> 步骤 {i}/{len(plan)}: {step_text}")
            if step_reason:
                print(f"   原因: {step_reason}")

            # 执行步骤
            # 新格式（tool + arguments）：直接调用工具，不经过LLM
            if step_tool and step_arguments:
                all_apis = get_all_apis()
                if step_arguments in all_apis:
                    print(f"   直接执行工具: {step_tool}")
                    api_info = all_apis[step_arguments]
                    # 构建工具参数：POST工具只需要 url、json、cookies
                    tool_arguments = {
                        "url": api_info.get("url", ""),
                        "json": api_info.get("json", {}),
                        "cookies": cookie,
                        "headers": api_info.get("headers", {}),
                    }
                    tool_call_dict = {"name": step_tool, "arguments": tool_arguments}
                    tool_call_result = await self._execute_tool(tool_call_dict)

                    # 执行失败时立即停止
                    if not tool_call_result.success:
                        error_msg = f"执行失败：步骤 {i} - {step_text}，失败原因: {tool_call_result.result}"
                        print(f"   ❌ {error_msg}")
                        turn.final_response = error_msg
                        turn.agent_reasoning = f"步骤 {i} 执行失败"
                        self.conversation_history.append(turn)
                        return error_msg

                    step_result = ""
                    if tool_call_result.result:
                        if isinstance(tool_call_result.result, dict):
                            output = tool_call_result.result.get("output", tool_call_result.result)
                        else:
                            output = tool_call_result.result
                        step_result = str(output) if not isinstance(output, str) else output
                    tc_results = [tool_call_result]
            else:
                # 旧格式（只有step描述）：经过LLM解释
                step_result, tc_results = await self._execute_step_with_tools(step_text, user_input, plan, results)

            # 构建 StepResult
            sr = StepResult(
                step=step_text,
                success=tc_results[0].success if tc_results else (step_result is not None),
                result=step_result,
                tool_calls=[{"name": tc.name, "arguments": tc.arguments, "success": tc.success} for tc in tc_results]
            )

            # 反思阶段
            if self.reflector:
                reflection = await self.reflector.reflect(step_text, sr)
                print(f"   反思结果: {reflection.reason}")

                if reflection.should_retry and self.reflector.should_continue_retrying(step_text):
                    # 重试
                    self.reflector.increment_retry(step_text)
                    for retry_round in range(self.reflector.max_retries):
                        print(f"   重试 {retry_round + 1}/{self.reflector.max_retries}...")
                        new_result, new_tc = await self._execute_step_with_tools(step_text, user_input, plan, results)
                        sr = StepResult(
                            step=step_text,
                            success=new_tc[0].success if new_tc else False,
                            result=new_result,
                            tool_calls=[{"name": tc.name, "arguments": tc.arguments, "success": tc.success} for tc in new_tc]
                        )
                        reflection = await self.reflector.reflect(step_text, sr)
                        if not reflection.should_retry:
                            break

                if reflection.should_replan:
                    # 重新规划剩余步骤
                    print(f"   检测到需要重新规划...")
                    remaining = plan[i:]  # 当前及之后的步骤
                    # 格式化剩余计划为可读文本
                    remaining_text = "\n".join([
                        f"{j+1}. {p.get('step', p) if isinstance(p, dict) else p}"
                        for j, p in enumerate(remaining)
                    ])
                    try:
                        new_plan = await self.planner.plan(
                            f"继续任务: {user_input}\n已完成: {results}\n剩余步骤:\n{remaining_text}",
                            available_tools=self._get_tool_definitions()
                        )
                        if new_plan and len(new_plan) < len(remaining):
                            print(f"   新计划缩短为 {len(new_plan)} 步")
                            # 替换剩余计划
                            plan = plan[:i] + new_plan
                    except Exception as e:
                        print(f"   重新规划失败: {e}")

                # 记录反思建议
                if reflection.suggestions:
                    print(f"   建议: {reflection.suggestions}")

            results.append(step_result or "")
            step_results.append(sr)

            print(f"   完成: {(step_result or '')[:80]}...")

        # 整体反思
        if self.reflector:
            try:
                reflection_summary = await self.reflector.reflect_on_plan(user_input, plan, step_results)
                if reflection_summary:
                    print(f"\n整体反思: {reflection_summary.get('overall_success', '未知')}")
            except Exception as e:
                print(f"整体反思失败: {e}")

        # 生成最终回复
        turn.final_response = self._format_plan_results(plan, results)
        turn.agent_reasoning = "复杂任务已完成"
        self.conversation_history.append(turn)

        return turn.final_response

    async def _execute_step_with_tools(
        self,
        step: str,
        user_input: str,
        plan: List[Dict],
        previous_results: List[str]
    ) -> tuple:
        """
        执行单个步骤及其工具调用

        Returns:
            (step_summary, tool_call_results)
        """
        # 构建步骤上下文
        # plan_item is now a dict with "step" and "reason" keys
        history_text = "\n\n".join([
            f"步骤 {j+1}: {plan[j].get('step', plan[j]) if isinstance(plan[j], dict) else plan[j]}\n结果: {previous_results[j]}"
            for j in range(len(previous_results))
        ]) if previous_results else "无"

        # 格式化当前计划
        plan_text = "\n".join([
            f"{j+1}. {p.get('step', p) if isinstance(p, dict) else p}"
            for j, p in enumerate(plan)
        ])

        step_context = f"""# 原始任务:
{user_input}

# 执行计划:
{plan_text}

# 历史步骤与结果:
{history_text}

# 当前步骤:
{step}

请执行当前步骤并给出结果。"""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": step_context}
        ]

        llm_response = await self.llm.chat(
            messages=messages,
            tools=self._get_tool_definitions()
        )

        content = llm_response.get("content", "")
        tool_calls = llm_response.get("tool_calls", [])

        tc_results = []
        for tool_call in tool_calls:
            result = await self._execute_tool(tool_call)
            tc_results.append(result)

        step_summary = content or "\n".join([
            f"{tc.name}: {'成功' if tc.success else '失败'}"
            for tc in tc_results
        ])

        return step_summary, tc_results

    def _format_plan_results(self, plan: List[Dict], results: List[str]) -> str:
        """格式化计划执行结果"""
        lines = ["**执行计划完成**\n"]

        for i, (step_dict, result) in enumerate(zip(plan, results), 1):
            # 支持新格式（tool + arguments）和旧格式（step）
            step_tool = step_dict.get("tool", "") if isinstance(step_dict, dict) else ""
            step_arguments = step_dict.get("arguments", {}) if isinstance(step_dict, dict) else {}
            step_text = step_dict.get("step", step_tool) if isinstance(step_dict, dict) else str(step_dict)
            reason_text = step_dict.get("reason", "") if isinstance(step_dict, dict) else ""

            lines.append(f"**步骤 {i}**: {step_text}")
            if step_tool and step_arguments:
                lines.append(f"   工具: {step_tool}")
                lines.append(f"   参数: {step_arguments}")
            if reason_text:
                lines.append(f"   原因: {reason_text}")
            lines.append(f"   结果: {result[:200] if result else '无'}...")
            lines.append("")

        lines.append(f"\n**总计**: 成功完成 {len(plan)} 个步骤")
        return "\n".join(lines)

    def _record_to_memory(self, user_input: str, result: str) -> None:
        """记录对话到工作记忆"""
        try:
            # 记录用户输入
            self.memory_manager.add_memory(
                content=f"用户: {user_input}",
                memory_type="working",
                importance=0.6,
                metadata={"type": "user_input"}
            )

            # 记录助手回复
            self.memory_manager.add_memory(
                content=f"助手: {result[:500]}..." if len(result) > 500 else f"助手: {result}",
                memory_type="working",
                importance=0.7,
                metadata={"type": "agent_response"}
            )
        except Exception as e:
            print(f"记录到记忆失败: {e}")

    def _build_prompt(self, user_input: str) -> str:
        """构建提示词"""
        context = f"\n当前状态："
        if self._authenticated:
            context += f"已登录，Cookies: {list(self._auth_cookies.keys())}"
        else:
            context += "未登录"

        if self._username:
            context += f"\n保存的凭证: {self._username} @ {self._base_url}"

        return f"""{self.system_prompt}

{context}

用户请求: {user_input}

请分析请求并决定使用哪些工具。
"""

    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取工具定义 - 优先使用MCP工具代理，否则使用MCP包装器，最后使用内置工具"""
        # 1. 优先使用MCP工具代理（统一网关模式）
        if self._mcp_proxy is not None:
            try:
                mcp_tools = self._mcp_proxy.list_tools()
                if mcp_tools:
                    print(f"可用MCPToolProxy工具: {[t.get('name') for t in mcp_tools]}")
                    return mcp_tools
            except Exception as e:
                print(f"MCPToolProxy获取工具失败: {e}")

        # 2. 回退到MCP包装器
        if self._mcp_wrapper is not None:
            mcp_tools = self._mcp_wrapper.list_tools()
            if mcp_tools:
                print(f"使用MCP包装器工具: {[t.get('name') for t in mcp_tools]}")
                return mcp_tools

        # 3. 回退到内置工具
        return self._get_builtin_tool_definitions()

    def _get_builtin_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取内置工具定义"""
        return [
            {
                "name": "LoginTool",
                "description": "API登录数栈平台（推荐方式）- 支持多环境",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "environment_name": {"type": "string", "description": "环境名称：如 '62'、'63'、'test'、'生产' 等。如未指定将自动推断。"},
                        "username": {"type": "string", "description": "用户名（可选，如已配置环境变量则无需提供）"},
                        "password": {"type": "string", "description": "密码（可选）"},
                        "base_url": {"type": "string", "description": "登录URL（可选，将根据environment_name自动选择）"}
                    }
                }
            },
            {
                "name": "Logout",
                "description": "登出指定环境（清除令牌）",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "environment_name": {"type": "string", "description": "环境名称（默认: default）"}
                    }
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
                "name": "memory_add",
                "description": "添加记忆",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "记忆内容"},
                        "memory_type": {"type": "string", "description": "记忆类型: working, episodic"},
                        "importance": {"type": "number", "description": "重要性: 0.0-1.0"}
                    },
                    "required": ["content"]
                }
            },
            {
                "name": "memory_search",
                "description": "搜索相关记忆",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索查询"}
                    },
                    "required": ["query"]
                }
            }
        ]

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> ToolCall:
        """执行工具调用"""
        name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})

        try:
            # 1. 优先尝试使用 MCP 工具代理（统一网关模式）
            if self._mcp_proxy is not None:
                try:
                    # 检查工具是否存在于代理中
                    mcp_tools = self._mcp_proxy.list_tools()
                    tool_names = [t.get('name') for t in mcp_tools]
                    if name in tool_names:
                        print(f"通过MCPToolProxy执行工具: {name}")
                        result_str = await self._mcp_proxy.call(name, arguments)
                        return ToolCall(
                            name=name,
                            arguments=arguments,
                            result={"output": result_str},
                            success=True
                        )
                except Exception as e:
                    print(f"MCPToolProxy执行工具 {name} 失败: {e}")

            # 2. 回退到 MCP 包装器
            if self._mcp_wrapper is not None:
                mcp_tools = self._mcp_wrapper.list_tools()
                tool_names = [t.get('name') for t in mcp_tools]
                if name in tool_names:
                    print(f"通过MCP包装器执行工具: {name}")
                    result_str = self._mcp_wrapper.run({
                        "action": "call_tool",
                        "tool_name": name,
                        "arguments": arguments
                    })
                    return ToolCall(
                        name=name,
                        arguments=arguments,
                        result={"output": result_str},
                        success=True
                    )

            # 3. 回退到内置工具
            if name == "LoginTool":
                result = await self._tool_login(**arguments)
            elif name == "Logout":
                result = await self._tool_logout(**arguments)
            elif name == "browser_get_cookies":
                result = await self._tool_browser_get_cookies()
            elif name == "http_request":
                result = await self._tool_http_request(**arguments)
            elif name == "memory_add":
                result = await self._tool_memory_add(**arguments)
            elif name == "memory_search":
                result = await self._tool_memory_search(**arguments)
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

    async def _tool_login(
        self,
        environment_name: str = "default",
        username: str = None,
        password: str = None,
        base_url: str = None
    ) -> Dict[str, Any]:
        """API登录工具"""
        import json
        import httpx

        # 确定登录URL和环境名
        if not base_url:
            # 根据环境名选择URL
            env_urls = {
                "62": "http://shuzhan62-online-test.k8s.dtstack.cn",
                "63": "http://shuzhan63-zdxx.k8s.dtstack.cn",
                "test": "http://shuzhan62-online-test.k8s.dtstack.cn",
                "default": "http://shuzhan62-online-test.k8s.dtstack.cn",
            }
            base_url = os.getenv(f"DATASTACK_{environment_name.upper()}_URL", env_urls.get(environment_name, env_urls["default"]))
        else:
            base_url = base_url.rstrip("/")

        # 如果环境名是default但URL包含63/62，自动推断
        if environment_name == "default":
            if "63" in base_url:
                environment_name = "63"
            elif "62" in base_url:
                environment_name = "62"

        # 如果没有用户名密码，尝试从环境变量获取
        if not username:
            username = os.getenv("DATASTACK_USERNAME")
        if not password:
            password = os.getenv("DATASTACK_PASSWORD")

        if not username or not password:
            return {
                "success": False,
                "message": "请提供用户名和密码，或配置 DATASTACK_USERNAME 和 DATASTACK_PASSWORD 环境变量",
                "environment_name": environment_name,
                "base_url": base_url
            }

        # 尝试API登录
        login_url = f"{base_url}/api/login"
        max_retries = 3
        last_error = ""

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(login_url, json={
                        "username": username,
                        "password": password
                    })
                    response_text = response.text

                    try:
                        resp_data = json.loads(response_text)
                    except:
                        resp_data = {"code": -1, "msg": response_text}

                    code = resp_data.get("code", -1)
                    msg = resp_data.get("msg", "")

                    if code == 0:
                        # 登录成功
                        data = resp_data.get("data", {})
                        token = data.get("token")

                        # 更新Agent状态
                        self._authenticated = True
                        self._username = username
                        self._password = password
                        self._base_url = base_url

                        # 保存token（通过环境变量共享给MCP工具）
                        if token:
                            os.environ[f"DATASTACK_{environment_name.upper()}_TOKEN"] = token

                        return {
                            "success": True,
                            "message": f"登录成功（环境: {environment_name}）",
                            "token": token[:20] + "..." if token else None,
                            "user_info": {
                                "username": username,
                                "environment_name": environment_name,
                                "base_url": base_url
                            }
                        }
                    elif "captcha" in msg.lower() or "验证码" in msg:
                        last_error = "需要验证码，请使用 browser_login 方式登录"
                        break
                    else:
                        last_error = msg
                        break

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP错误 {e.response.status_code}"
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue

        return {
            "success": False,
            "message": f"登录失败: {last_error}",
            "environment_name": environment_name
        }

    async def _tool_logout(self, environment_name: str = "default") -> Dict[str, Any]:
        """登出工具"""
        token_key = f"DATASTACK_{environment_name.upper()}_TOKEN"
        if token_key in os.environ:
            del os.environ[token_key]

        if self._authenticated and self._base_url:
            # 检查是否是当前登录的环境
            pass

        self._authenticated = False

        return {
            "success": True,
            "message": f"已登出环境 {environment_name}"
        }

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

        if headers is None:
            headers = {}

        # 优先使用 Bearer Token（API登录后存储在环境变量）
        if self._authenticated:
            # 尝试从环境变量获取token
            for env_name in ["62", "63", "DEFAULT"]:
                token_key = f"DATASTACK_{env_name.upper()}_TOKEN"
                token = os.getenv(token_key)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    break

        # 回退到使用 cookies
        if self._authenticated and self._auth_cookies and "Authorization" not in headers:
            cookie_str = "; ".join([f"{k}={v}" for k, v in self._auth_cookies.items()])
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

    async def _tool_memory_add(
        self,
        content: str,
        memory_type: str = "working",
        importance: float = 0.5
    ) -> Dict[str, Any]:
        """记忆添加工具"""
        try:
            memory_id = self.memory_manager.add_memory(
                content=content,
                memory_type=memory_type,
                importance=importance
            )
            return {"success": True, "memory_id": memory_id}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_memory_search(self, query: str) -> Dict[str, Any]:
        """记忆搜索工具"""
        try:
            results = self.memory_manager.retrieve_memories(
                query=query,
                limit=5
            )
            return {
                "success": True,
                "count": len(results),
                "results": [
                    {
                        "id": r.id,
                        "content": r.content[:100],
                        "importance": r.importance
                    }
                    for r in results
                ]
            }
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
