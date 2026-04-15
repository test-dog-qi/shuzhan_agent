"""记忆工具 - 统一入口，分发处理"""

from typing import Dict, Any, List
from datetime import datetime

import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shuzhan_agent.tools.base import Tool, ToolParameter
from shuzhan_agent.memory.manager import MemoryManager
from shuzhan_agent.memory.base import MemoryConfig


class MemoryTool(Tool):
    """
    记忆工具 - 统一入口，分发处理

    提供记忆功能：
    - add: 添加记忆
    - search: 搜索记忆
    - summary: 获取记忆摘要
    - stats: 获取统计信息
    - update: 更新记忆
    - remove: 删除记忆
    - forget: 遗忘记忆
    - consolidate: 整合记忆
    - clear_all: 清空所有记忆
    """

    def __init__(self, user_id: str = "default_user", config: MemoryConfig = None):
        super().__init__(
            name="memory",
            description="记忆工具 - 存储和检索对话历史、知识和经验"
        )
        load_dotenv()

        # 初始化记忆管理器
        self.memory_config = config or MemoryConfig()
        self.memory_config.qdrant_url = os.getenv("QDRANT_URL", self.memory_config.qdrant_url)
        self.memory_config.qdrant_api_key = os.getenv("QDRANT_API_KEY", self.memory_config.qdrant_api_key)
        self.memory_config.qdrant_collection = os.getenv("QDRANT_COLLECTION", self.memory_config.qdrant_collection)
        self.memory_config.embed_model_type = os.getenv("EMBED_MODEL_TYPE", self.memory_config.embed_model_type)
        self.memory_config.embed_model_name = os.getenv("EMBED_MODEL_NAME", self.memory_config.embed_model_name)

        self.memory_manager = MemoryManager(
            config=self.memory_config,
            user_id=user_id,
            enable_working=True,
            enable_episodic=True
        )

        self.current_session_id = None
        self.conversation_count = 0

    def run(self, parameters: Dict[str, Any]) -> str:
        """执行工具"""
        if not self.validate_parameters(parameters):
            return "参数验证失败：缺少必需的参数"

        action = parameters.get("action")
        kwargs = {k: v for k, v in parameters.items() if k != "action"}

        return self.execute(action, **kwargs)

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="操作: add, search, summary, stats, update, remove, forget, consolidate, clear_all, save_credentials, get_credentials",
                required=True
            ),
            ToolParameter(name="content", type="string", description="记忆内容", required=False),
            ToolParameter(name="query", type="string", description="搜索查询", required=False),
            ToolParameter(name="memory_type", type="string", description="记忆类型: working, episodic", required=False, default="working"),
            ToolParameter(name="importance", type="number", description="重要性: 0.0-1.0", required=False),
            ToolParameter(name="limit", type="integer", description="结果数量限制", required=False, default=5),
            ToolParameter(name="memory_id", type="string", description="记忆ID", required=False),
            ToolParameter(name="strategy", type="string", description="遗忘策略", required=False, default="importance_based"),
            ToolParameter(name="threshold", type="number", description="遗忘阈值", required=False, default=0.1),
            ToolParameter(name="max_age_days", type="integer", description="最大保留天数", required=False, default=30),
            ToolParameter(name="from_type", type="string", description="整合来源类型", required=False, default="working"),
            ToolParameter(name="to_type", type="string", description="整合目标类型", required=False, default="episodic"),
            ToolParameter(name="importance_threshold", type="number", description="整合重要性阈值", required=False, default=0.7),
            ToolParameter(name="username", type="string", description="用户名", required=False),
            ToolParameter(name="password", type="string", description="密码", required=False),
            ToolParameter(name="base_url", type="string", description="平台地址", required=False),
            ToolParameter(name="environment_name", type="string", description="环境名称", required=False, default="default"),
        ]

    def execute(self, action: str, **kwargs) -> str:
        """执行记忆操作"""
        if action == "add":
            return self._add_memory(**kwargs)
        elif action == "search":
            return self._search_memory(**kwargs)
        elif action == "summary":
            return self._get_summary(**kwargs)
        elif action == "stats":
            return self._get_stats()
        elif action == "update":
            return self._update_memory(**kwargs)
        elif action == "remove":
            return self._remove_memory(**kwargs)
        elif action == "forget":
            return self._forget(**kwargs)
        elif action == "consolidate":
            return self._consolidate(**kwargs)
        elif action == "clear_all":
            return self._clear_all()
        elif action == "save_credentials":
            return self._save_credentials(**kwargs)
        elif action == "get_credentials":
            return self._get_credentials(**kwargs)
        else:
            return f"不支持的操作: {action}"

    def _save_credentials(self, username: str = None, password: str = None,
                         base_url: str = None, environment_name: str = "default", **kwargs) -> str:
        """保存凭证"""
        if not username or not password or not base_url:
            return "保存凭证失败: 缺少 username, password 或 base_url"
        return self.save_credentials(username, password, base_url, environment_name)

    def _get_credentials(self, environment_name: str = "default", **kwargs) -> str:
        """获取凭证"""
        return self.get_credentials(environment_name)

    def _add_memory(self, content: str = "", memory_type: str = "working",
                    importance: float = 0.5, **metadata) -> str:
        try:
            if self.current_session_id is None:
                self.current_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            metadata.update({
                "session_id": self.current_session_id,
                "timestamp": datetime.now().isoformat()
            })

            memory_id = self.memory_manager.add_memory(
                content=content,
                memory_type=memory_type,
                importance=importance,
                metadata=metadata,
                auto_classify=False
            )

            return f"记忆已添加 (ID: {memory_id[:8]}...)"

        except Exception as e:
            return f"添加记忆失败: {str(e)}"

    def _search_memory(self, query: str, limit: int = 5, memory_types: List[str] = None,
                        memory_type: str = None, min_importance: float = 0.1) -> str:
        try:
            if memory_type and not memory_types:
                memory_types = [memory_type]

            results = self.memory_manager.retrieve_memories(
                query=query, limit=limit, memory_types=memory_types, min_importance=min_importance
            )

            if not results:
                return f"未找到与 '{query}' 相关的记忆"

            formatted_results = [f"找到 {len(results)} 条相关记忆:"]

            for i, memory in enumerate(results, 1):
                type_label = {"working": "工作记忆", "episodic": "情景记忆"}.get(memory.memory_type, memory.memory_type)
                content_preview = memory.content[:80] + "..." if len(memory.content) > 80 else memory.content
                formatted_results.append(f"{i}. [{type_label}] {content_preview} (重要性: {memory.importance:.2f})")

            return "\n".join(formatted_results)

        except Exception as e:
            return f"搜索记忆失败: {str(e)}"

    def _get_summary(self, limit: int = 10) -> str:
        try:
            stats = self.memory_manager.get_memory_stats()

            summary_parts = [
                f"记忆系统摘要",
                f"总记忆数: {stats['total_memories']}",
                f"当前会话: {self.current_session_id or '未开始'}",
                f"对话轮次: {self.conversation_count}"
            ]

            if stats['memories_by_type']:
                summary_parts.append("\n记忆类型分布:")
                for memory_type, type_stats in stats['memories_by_type'].items():
                    count = type_stats.get('count', 0)
                    avg_importance = type_stats.get('avg_importance', 0)
                    type_label = {"working": "工作记忆", "episodic": "情景记忆"}.get(memory_type, memory_type)
                    summary_parts.append(f"  • {type_label}: {count} 条 (平均重要性: {avg_importance:.2f})")

            return "\n".join(summary_parts)

        except Exception as e:
            return f"获取摘要失败: {str(e)}"

    def _get_stats(self) -> str:
        try:
            stats = self.memory_manager.get_memory_stats()

            stats_info = [
                f"记忆系统统计",
                f"总记忆数: {stats['total_memories']}",
                f"启用的记忆类型: {', '.join(stats['enabled_types'])}",
                f"会话ID: {self.current_session_id or '未开始'}",
                f"对话轮次: {self.conversation_count}"
            ]

            return "\n".join(stats_info)

        except Exception as e:
            return f"获取统计信息失败: {str(e)}"

    def _update_memory(self, memory_id: str, content: str = None, importance: float = None, **metadata) -> str:
        try:
            success = self.memory_manager.update_memory(
                memory_id=memory_id, content=content, importance=importance, metadata=metadata or None
            )
            return "记忆已更新" if success else "未找到要更新的记忆"
        except Exception as e:
            return f"更新记忆失败: {str(e)}"

    def _remove_memory(self, memory_id: str) -> str:
        try:
            success = self.memory_manager.remove_memory(memory_id)
            return "记忆已删除" if success else "未找到要删除的记忆"
        except Exception as e:
            return f"删除记忆失败: {str(e)}"

    def _forget(self, strategy: str = "importance_based", threshold: float = 0.1, max_age_days: int = 30) -> str:
        try:
            count = self.memory_manager.forget_memories(
                strategy=strategy, threshold=threshold, max_age_days=max_age_days
            )
            return f"已遗忘 {count} 条记忆（策略: {strategy}）"
        except Exception as e:
            return f"遗忘记忆失败: {str(e)}"

    def _consolidate(self, from_type: str = "working", to_type: str = "episodic", importance_threshold: float = 0.7) -> str:
        try:
            count = self.memory_manager.consolidate_memories(
                from_type=from_type, to_type=to_type, importance_threshold=importance_threshold
            )
            return f"已整合 {count} 条记忆（{from_type} → {to_type}，阈值={importance_threshold}）"
        except Exception as e:
            return f"整合记忆失败: {str(e)}"

    def _clear_all(self) -> str:
        try:
            self.memory_manager.clear_all_memories()
            return "已清空所有记忆"
        except Exception as e:
            return f"清空记忆失败: {str(e)}"

    def auto_record_conversation(self, user_input: str, agent_response: str):
        """自动记录对话"""
        self.conversation_count += 1
        self._add_memory(
            content=f"用户: {user_input}",
            memory_type="working",
            importance=0.6,
            type="user_input",
            conversation_id=self.conversation_count
        )
        self._add_memory(
            content=f"助手: {agent_response}",
            memory_type="working",
            importance=0.7,
            type="agent_response",
            conversation_id=self.conversation_count
        )

    def get_context_for_query(self, query: str, limit: int = 3) -> str:
        """获取相关上下文"""
        results = self.memory_manager.retrieve_memories(query=query, limit=limit, min_importance=0.3)
        if not results:
            return ""
        context_parts = ["相关记忆:"]
        for memory in results:
            context_parts.append(f"- {memory.content}")
        return "\n".join(context_parts)

    def save_credentials(self, username: str, password: str, base_url: str,
                         environment_name: str = "default") -> str:
        """
        保存登录凭证到情景记忆

        Args:
            username: 用户名
            password: 密码
            base_url: 平台地址
            environment_name: 环境名称

        Returns:
            保存结果消息
        """
        try:
            content = f"DATASTACK_CREDENTIALS: 环境={environment_name}, 用户名={username}, 平台={base_url}"
            memory_id = self.memory_manager.add_memory(
                content=content,
                memory_type="episodic",
                importance=0.9,
                metadata={
                    "type": "credential",
                    "username": username,
                    "base_url": base_url,
                    "environment_name": environment_name,
                    "sensitive": True
                },
                auto_classify=False
            )
            return f"凭证已保存 (ID: {memory_id[:8]}...)"
        except Exception as e:
            return f"保存凭证失败: {str(e)}"

    def get_credentials(self, environment_name: str = "default") -> str:
        """
        获取保存的凭证

        Args:
            environment_name: 环境名称

        Returns:
            凭证信息（不包含密码明文）或未找到消息
        """
        try:
            results = self.memory_manager.retrieve_memories(
                query=f"DATASTACK_CREDENTIALS {environment_name}",
                memory_types=["episodic"],
                limit=5
            )
            creds = [m for m in results if m.metadata.get("type") == "credential"]
            if not creds:
                return f"未找到 {environment_name} 的凭证"

            # 返回最新的
            latest = max(creds, key=lambda m: m.timestamp)
            return (f"找到凭证 - 用户名: {latest.metadata.get('username')}, "
                    f"环境: {latest.metadata.get('environment_name')}, "
                    f"保存时间: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            return f"获取凭证失败: {str(e)}"

    def clear_session(self):
        """清除当前会话"""
        self.current_session_id = None
        self.conversation_count = 0
        wm = self.memory_manager.memory_types.get('working')
        if wm:
            wm.clear()
