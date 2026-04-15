"""上下文工程模块 - GSSC 流水线实现

实现 Gather-Select-Structure-Compress 上下文构建流程：
1. Gather: 从多源收集候选信息（记忆、历史、工具结果）
2. Select: 基于优先级、相关性、新近性筛选
3. Structure: 组织成结构化上下文模板
4. Compress: 在预算内压缩与规范化

参考 hello_agents/context/builder.py 实现
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import math

from shuzhan_agent.memory.base import MemoryItem


@dataclass
class ContextPacket:
    """上下文信息包"""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    relevance_score: float = 0.0  # 0.0-1.0

    def __post_init__(self):
        """自动计算token数"""
        if self.token_count == 0:
            self.token_count = count_tokens(self.content)


@dataclass
class ContextConfig:
    """上下文构建配置"""
    max_tokens: int = 8000  # 总预算
    reserve_ratio: float = 0.15  # 生成余量（10-20%）
    min_relevance: float = 0.3  # 最小相关性阈值
    enable_mmr: bool = True  # 启用最大边际相关性（多样性）
    mmr_lambda: float = 0.7  # MMR平衡参数（0=纯多样性, 1=纯相关性）
    enable_compression: bool = True  # 启用压缩

    def get_available_tokens(self) -> int:
        """获取可用token预算（扣除余量）"""
        return int(self.max_tokens * (1 - self.reserve_ratio))


class ContextEngine:
    """上下文构建器 - GSSC流水线

    用法示例：
    ```python
    context_engine = ContextEngine(
        config=ContextConfig(max_tokens=8000)
    )

    context = context_engine.build(
        user_query="用户问题",
        conversation_history=[...],
        system_instructions="系统指令"
    )
    ```
    """

    def __init__(self, config: ContextConfig = None):
        self.config = config or ContextConfig()

    def build(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict]] = None,
        system_instructions: Optional[str] = None,
        memory_results: Optional[List[MemoryItem]] = None,
        tool_results: Optional[List[Dict]] = None
    ) -> str:
        """构建完整上下文

        Args:
            user_query: 用户查询
            conversation_history: 对话历史
            system_instructions: 系统指令
            memory_results: 从记忆模块检索的结果
            tool_results: 工具执行结果

        Returns:
            结构化上下文字符串
        """
        # 1. Gather: 收集候选信息
        packets = self._gather(
            user_query=user_query,
            conversation_history=conversation_history or [],
            system_instructions=system_instructions,
            memory_results=memory_results or [],
            tool_results=tool_results or []
        )

        # 2. Select: 筛选与排序
        selected_packets = self._select(packets, user_query)

        # 3. Structure: 组织成结构化模板
        structured_context = self._structure(
            selected_packets=selected_packets,
            user_query=user_query,
            system_instructions=system_instructions
        )

        # 4. Compress: 压缩与规范化（如果超预算）
        final_context = self._compress(structured_context)

        return final_context

    def _gather(
        self,
        user_query: str,
        conversation_history: List[Dict],
        system_instructions: Optional[str],
        memory_results: List[MemoryItem],
        tool_results: List[Dict]
    ) -> List[ContextPacket]:
        """Gather: 收集候选信息"""
        packets = []

        # P0: 系统指令（强约束）
        if system_instructions:
            packets.append(ContextPacket(
                content=system_instructions,
                metadata={"type": "instructions"}
            ))

        # P1: 相关记忆（从记忆模块检索）
        if memory_results:
            for memory in memory_results:
                packets.append(ContextPacket(
                    content=f"[记忆] {memory.content}",
                    timestamp=memory.timestamp,
                    metadata={"type": "related_memory", "memory_type": memory.memory_type}
                ))

        # P2: 工具执行结果
        if tool_results:
            for tool_result in tool_results:
                packets.append(ContextPacket(
                    content=f"[工具: {tool_result.get('name', 'unknown')}] {tool_result.get('result', '')}",
                    metadata={"type": "tool_result", "tool_name": tool_result.get('name')}
                ))

        # P3: 对话历史（辅助材料）
        if conversation_history:
            # 只保留最近10条
            recent_history = conversation_history[-10:]
            history_text = "\n".join([
                f"[{msg.get('role', 'user')}] {msg.get('content', '')}"
                for msg in recent_history
            ])
            packets.append(ContextPacket(
                content=history_text,
                metadata={"type": "history", "count": len(recent_history)}
            ))

        return packets

    def _select(
        self,
        packets: List[ContextPacket],
        user_query: str
    ) -> List[ContextPacket]:
        """Select: 基于分数与预算的筛选"""
        # 1) 计算相关性（关键词重叠）
        query_tokens = set(user_query.lower().split())
        for packet in packets:
            content_tokens = set(packet.content.lower().split())
            if len(query_tokens) > 0:
                overlap = len(query_tokens & content_tokens)
                packet.relevance_score = overlap / len(query_tokens)
            else:
                packet.relevance_score = 0.0

        # 2) 计算新近性（指数衰减）
        def recency_score(ts: datetime) -> float:
            delta = max((datetime.now() - ts).total_seconds(), 0)
            tau = 3600  # 1小时时间尺度
            return math.exp(-delta / tau)

        # 3) 计算复合分：0.7*相关性 + 0.3*新近性
        scored_packets: List[tuple] = []
        for p in packets:
            rec = recency_score(p.timestamp)
            score = 0.7 * p.relevance_score + 0.3 * rec
            scored_packets.append((score, p))

        # 4) 系统指令单独拿出，固定纳入
        system_packets = [p for (_, p) in scored_packets if p.metadata.get("type") == "instructions"]
        remaining = [p for (s, p) in sorted(scored_packets, key=lambda x: x[0], reverse=True)
                     if p.metadata.get("type") != "instructions"]

        # 5) 依据 min_relevance 过滤（对非系统包）
        filtered = [p for p in remaining if p.relevance_score >= self.config.min_relevance]

        # 6) 按预算填充
        available_tokens = self.config.get_available_tokens()
        selected: List[ContextPacket] = []
        used_tokens = 0

        # 先放入系统指令（不排序）
        for p in system_packets:
            if used_tokens + p.token_count <= available_tokens:
                selected.append(p)
                used_tokens += p.token_count

        # 再按分数加入其余
        for p in filtered:
            if used_tokens + p.token_count > available_tokens:
                continue
            selected.append(p)
            used_tokens += p.token_count

        return selected

    def _structure(
        self,
        selected_packets: List[ContextPacket],
        user_query: str,
        system_instructions: Optional[str]
    ) -> str:
        """Structure: 组织成结构化上下文模板"""
        sections = []

        # [Role & Policies] - 系统指令
        p0_packets = [p for p in selected_packets if p.metadata.get("type") == "instructions"]
        if p0_packets:
            role_section = "[Role & Policies]\n"
            role_section += "\n".join([p.content for p in p0_packets])
            sections.append(role_section)

        # [Task] - 当前任务
        sections.append(f"[Task]\n用户问题：{user_query}")

        # [State] - 任务状态
        p1_packets = [p for p in selected_packets if p.metadata.get("type") == "task_state"]
        if p1_packets:
            state_section = "[State]\n关键进展与未决问题：\n"
            state_section += "\n".join([p.content for p in p1_packets])
            sections.append(state_section)

        # [Evidence] - 事实证据（记忆、工具结果）
        p2_packets = [
            p for p in selected_packets
            if p.metadata.get("type") in {"related_memory", "tool_result"}
        ]
        if p2_packets:
            evidence_section = "[Evidence]\n事实与引用：\n"
            for p in p2_packets:
                evidence_section += f"\n{p.content}\n"
            sections.append(evidence_section)

        # [Context] - 辅助材料（历史等）
        p3_packets = [p for p in selected_packets if p.metadata.get("type") == "history"]
        if p3_packets:
            context_section = "[Context]\n对话历史与背景：\n"
            context_section += "\n".join([p.content for p in p3_packets])
            sections.append(context_section)

        # [Output] - 输出约束
        output_section = """[Output]
请按以下格式回答：
1. 结论（简洁明确）
2. 依据（列出支撑证据及来源）
3. 风险与假设（如有）
4. 下一步行动建议（如适用）"""
        sections.append(output_section)

        return "\n\n".join(sections)

    def _compress(self, context: str) -> str:
        """Compress: 压缩与规范化"""
        if not self.config.enable_compression:
            return context

        current_tokens = count_tokens(context)
        available_tokens = self.config.get_available_tokens()

        if current_tokens <= available_tokens:
            return context

        # 按段落截断，保留结构
        print(f"上下文超预算 ({current_tokens} > {available_tokens})，执行截断")

        lines = context.split("\n")
        compressed_lines = []
        used_tokens = 0

        for line in lines:
            line_tokens = count_tokens(line)
            if used_tokens + line_tokens > available_tokens:
                break
            compressed_lines.append(line)
            used_tokens += line_tokens

        return "\n".join(compressed_lines)


def count_tokens(text: str) -> int:
    """计算文本token数（使用粗略估算）"""
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # 降级方案：粗略估算（1 token ≈ 4 字符）
        return len(text) // 4
