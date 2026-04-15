"""记忆管理器 - 统一管理接口"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging

from .base import MemoryItem, MemoryConfig, BaseMemory
from .working import WorkingMemory
from .episodic import EpisodicMemory

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器 - 统一的记忆操作接口

    支持的记忆类型：
    - working: 工作记忆（TTL管理，纯内存）
    - episodic: 情景记忆（SQLite + Qdrant）
    """

    def __init__(self, config: Optional[MemoryConfig] = None, user_id: str = "default_user",
                 enable_working: bool = True, enable_episodic: bool = True):
        self.config = config or MemoryConfig()
        self.user_id = user_id
        self.memory_types: Dict[str, BaseMemory] = {}

        if enable_working:
            self.memory_types['working'] = WorkingMemory(self.config)

        if enable_episodic:
            self.memory_types['episodic'] = EpisodicMemory(self.config)

        logger.info(f"MemoryManager初始化完成，启用记忆类型: {list(self.memory_types.keys())}")

    def add_memory(self, content: str, memory_type: str = "working",
                    importance: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None,
                    auto_classify: bool = True) -> str:
        if auto_classify:
            memory_type = self._classify_memory_type(content, metadata)

        if importance is None:
            importance = self._calculate_importance(content, metadata)

        memory_item = MemoryItem(
            id=str(uuid.uuid4()),
            content=content,
            memory_type=memory_type,
            user_id=self.user_id,
            timestamp=datetime.now(),
            importance=importance,
            metadata=metadata or {}
        )

        if memory_type in self.memory_types:
            memory_id = self.memory_types[memory_type].add(memory_item)
            return memory_id
        else:
            raise ValueError(f"不支持的记忆类型: {memory_type}")

    def retrieve_memories(self, query: str, memory_types: Optional[List[str]] = None,
                           limit: int = 10, min_importance: float = 0.0,
                           time_range: Optional[tuple] = None) -> List[MemoryItem]:
        if memory_types is None:
            memory_types = list(self.memory_types.keys())

        all_results = []
        per_type_limit = max(1, limit // len(memory_types))

        for memory_type in memory_types:
            if memory_type in self.memory_types:
                memory_instance = self.memory_types[memory_type]
                try:
                    type_results = memory_instance.retrieve(
                        query=query, limit=per_type_limit, user_id=self.user_id
                    )
                    all_results.extend(type_results)
                except Exception as e:
                    logger.warning(f"检索 {memory_type} 记忆时出错: {e}")
                    continue

        all_results.sort(key=lambda x: x.importance, reverse=True)
        return all_results[:limit]

    def update_memory(self, memory_id: str, content: Optional[str] = None,
                      importance: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
        for memory_type, memory_instance in self.memory_types.items():
            if memory_instance.has_memory(memory_id):
                return memory_instance.update(memory_id, content, importance, metadata)

        return False

    def remove_memory(self, memory_id: str) -> bool:
        for memory_type, memory_instance in self.memory_types.items():
            if memory_instance.has_memory(memory_id):
                return memory_instance.remove(memory_id)

        return False

    def forget_memories(self, strategy: str = "importance_based", threshold: float = 0.1, max_age_days: int = 30) -> int:
        total_forgotten = 0

        for memory_type, memory_instance in self.memory_types.items():
            if hasattr(memory_instance, 'forget'):
                forgotten = memory_instance.forget(strategy, threshold, max_age_days)
                total_forgotten += forgotten

        return total_forgotten

    def consolidate_memories(self, from_type: str = "working", to_type: str = "episodic",
                           importance_threshold: float = 0.7) -> int:
        if from_type not in self.memory_types or to_type not in self.memory_types:
            return 0

        source_memory = self.memory_types[from_type]
        target_memory = self.memory_types[to_type]

        all_memories = source_memory.get_all()
        candidates = [m for m in all_memories if m.importance >= importance_threshold]

        consolidated_count = 0
        for memory in candidates:
            if source_memory.remove(memory.id):
                memory.memory_type = to_type
                memory.importance *= 1.1
                target_memory.add(memory)
                consolidated_count += 1

        return consolidated_count

    def get_memory_stats(self) -> Dict[str, Any]:
        stats = {
            "user_id": self.user_id,
            "enabled_types": list(self.memory_types.keys()),
            "total_memories": 0,
            "memories_by_type": {}
        }

        for memory_type, memory_instance in self.memory_types.items():
            type_stats = memory_instance.get_stats()
            stats["memories_by_type"][memory_type] = type_stats
            stats["total_memories"] += type_stats.get("count", 0)

        return stats

    def clear_all_memories(self):
        for memory_type, memory_instance in self.memory_types.items():
            memory_instance.clear()

    def _classify_memory_type(self, content: str, metadata: Optional[Dict[str, Any]]) -> str:
        # 注意：metadata["type"] 可能包含 "user_input" 等值，但这些不是有效的记忆类型
        # 只根据内容自动分类，不依赖 metadata["type"]
        if self._is_episodic_content(content):
            return "episodic"
        return "working"

    def _is_episodic_content(self, content: str) -> bool:
        episodic_keywords = ["昨天", "今天", "明天", "上次", "记得", "发生", "经历"]
        return any(keyword in content for keyword in episodic_keywords)

    def _calculate_importance(self, content: str, metadata: Optional[Dict[str, Any]]) -> float:
        importance = 0.5

        if len(content) > 100:
            importance += 0.1

        important_keywords = ["重要", "关键", "必须", "注意", "警告", "错误"]
        if any(keyword in content for keyword in important_keywords):
            importance += 0.2

        if metadata:
            if metadata.get("priority") == "high":
                importance += 0.3
            elif metadata.get("priority") == "low":
                importance -= 0.2

        return max(0.0, min(1.0, importance))

    def __str__(self) -> str:
        stats = self.get_memory_stats()
        return f"MemoryManager(user={self.user_id}, total={stats['total_memories']})"
