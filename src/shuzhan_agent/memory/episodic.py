"""情景记忆实现 - SQLite + Qdrant"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

from .base import BaseMemory, MemoryItem, MemoryConfig
from .storage import SQLiteDocumentStore
from .vector_store import QdrantConnectionManager, QDRANT_AVAILABLE
from .embedding import get_embedder


class Episode:
    """情景记忆中的单个情景"""

    def __init__(self, episode_id: str, user_id: str, session_id: str, timestamp: datetime,
                 content: str, context: Dict[str, Any], outcome: Optional[str] = None, importance: float = 0.5):
        self.episode_id = episode_id
        self.user_id = user_id
        self.session_id = session_id
        self.timestamp = timestamp
        self.content = content
        self.context = context
        self.outcome = outcome
        self.importance = importance


class SimpleEmbedder:
    """简单的TF-IDF嵌入（无外部依赖时使用）"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._vocab = {}
        self._idf = {}
        self._fitted = False

    def encode(self, texts: str) -> List[float]:
        if isinstance(texts, str):
            texts = [texts]

        if not self._fitted:
            return [0.0] * self.dimension

        results = []
        for text in texts:
            words = text.lower().split()
            vector = [0.0] * self.dimension
            for word in words:
                if word in self._vocab:
                    idx = self._vocab[word]
                    tf = words.count(word)
                    vector[idx] = tf * self._idf.get(word, 1.0)
            results.append(vector)

        return results[0] if len(texts) == 1 else results


class EpisodicMemory(BaseMemory):
    """
    情景记忆实现

    特点：
    - 存储具体的交互事件
    - SQLite权威存储 + Qdrant向量检索
    - 支持按时间序列或主题检索
    """

    def __init__(self, config: MemoryConfig, storage_backend=None):
        super().__init__(config, storage_backend)

        self.episodes: List[Episode] = []
        self.sessions: Dict[str, List[str]] = {}

        # SQLite存储
        db_dir = self.config.storage_path
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "memory.db")
        self.doc_store = SQLiteDocumentStore(db_path=db_path)

        # 嵌入模型（优先 text-embedding-v4，兜底 sentence-transformers）
        try:
            from .embedding import refresh_embedder
            self.embedder = refresh_embedder()
            # 更新配置中的向量维度以匹配实际的 embedder 维度
            self.config.qdrant_vector_size = self.embedder.dimension
        except Exception as e:
            logger.warning(f"嵌入模型初始化失败: {e}，使用 SimpleEmbedder 兜底")
            self.embedder = SimpleEmbedder(dimension=self.config.qdrant_vector_size)

        # Qdrant向量存储
        self.vector_store = None
        if QDRANT_AVAILABLE and self.config.qdrant_url:
            try:
                self.vector_store = QdrantConnectionManager.get_instance(
                    url=self.config.qdrant_url,
                    api_key=self.config.qdrant_api_key,
                    collection_name=self.config.qdrant_collection,
                    vector_size=self.config.qdrant_vector_size,
                    distance=self.config.qdrant_distance
                )
            except Exception as e:
                logger.warning(f"Qdrant连接失败: {e}")

    def add(self, memory_item: MemoryItem) -> str:
        session_id = memory_item.metadata.get("session_id", "default_session")
        context = memory_item.metadata.get("context", {})
        outcome = memory_item.metadata.get("outcome")
        participants = memory_item.metadata.get("participants", [])
        tags = memory_item.metadata.get("tags", [])

        episode = Episode(
            episode_id=memory_item.id,
            user_id=memory_item.user_id,
            session_id=session_id,
            timestamp=memory_item.timestamp,
            content=memory_item.content,
            context=context,
            outcome=outcome,
            importance=memory_item.importance
        )
        self.episodes.append(episode)
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(episode.episode_id)

        # SQLite存储 - 合并额外元数据到 properties
        ts_int = int(memory_item.timestamp.timestamp())
        properties = {
            "session_id": session_id,
            "context": context,
            "outcome": outcome,
            "participants": participants,
            "tags": tags
        }
        # 合并 memory_item.metadata 中的额外字段
        for key, value in memory_item.metadata.items():
            if key not in properties:
                properties[key] = value

        self.doc_store.add_memory(
            memory_id=memory_item.id,
            user_id=memory_item.user_id,
            content=memory_item.content,
            memory_type="episodic",
            timestamp=ts_int,
            importance=memory_item.importance,
            properties=properties
        )

        # Qdrant向量索引
        if self.vector_store:
            try:
                embedding = self.embedder.encode(memory_item.content)
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                self.vector_store.add_vectors(
                    vectors=[embedding],
                    metadata=[{
                        "memory_id": memory_item.id,
                        "user_id": memory_item.user_id,
                        "memory_type": "episodic",
                        "importance": memory_item.importance,
                        "session_id": session_id,
                        "content": memory_item.content
                    }],
                    ids=[memory_item.id]
                )
            except Exception as e:
                logger.warning(f"向量入库失败: {e}")

        return memory_item.id

    def retrieve(self, query: str, limit: int = 5, **kwargs) -> List[MemoryItem]:
        user_id = kwargs.get("user_id")
        session_id = kwargs.get("session_id")
        time_range: Optional[Tuple[datetime, datetime]] = kwargs.get("time_range")
        importance_threshold: Optional[float] = kwargs.get("importance_threshold")

        candidate_ids: Optional[set] = None
        if time_range is not None or importance_threshold is not None:
            start_ts = int(time_range[0].timestamp()) if time_range else None
            end_ts = int(time_range[1].timestamp()) if time_range else None
            docs = self.doc_store.search_memories(
                user_id=user_id,
                memory_type="episodic",
                start_time=start_ts,
                end_time=end_ts,
                importance_threshold=importance_threshold,
                limit=1000
            )
            candidate_ids = {d["memory_id"] for d in docs}

        # 向量检索
        results: List[Tuple[float, MemoryItem]] = []
        if self.vector_store:
            try:
                query_vec = self.embedder.encode(query)
                if hasattr(query_vec, 'tolist'):
                    query_vec = query_vec.tolist()
                where = {"memory_type": "episodic"}
                if user_id:
                    where["user_id"] = user_id
                hits = self.vector_store.search_similar(query_vector=query_vec, limit=max(limit * 5, 20), where=where)

                now_ts = int(datetime.now().timestamp())
                seen = set()
                for hit in hits:
                    meta = hit.get("metadata", {})
                    mem_id = meta.get("memory_id")
                    if not mem_id or mem_id in seen:
                        continue

                    episode = next((e for e in self.episodes if e.episode_id == mem_id), None)
                    if episode and episode.context.get("forgotten", False):
                        continue

                    if candidate_ids is not None and mem_id not in candidate_ids:
                        continue
                    if session_id and meta.get("session_id") != session_id:
                        continue

                    doc = self.doc_store.get_memory(mem_id)
                    if not doc:
                        continue

                    vec_score = float(hit.get("score", 0.0))
                    age_days = max(0.0, (now_ts - int(doc["timestamp"])) / 86400.0)
                    recency_score = 1.0 / (1.0 + age_days)
                    imp = float(doc.get("importance", 0.5))

                    base_relevance = vec_score * 0.8 + recency_score * 0.2
                    importance_weight = 0.8 + (imp * 0.4)
                    combined = base_relevance * importance_weight

                    item = MemoryItem(
                        id=doc["memory_id"],
                        content=doc["content"],
                        memory_type=doc["memory_type"],
                        user_id=doc["user_id"],
                        timestamp=datetime.fromtimestamp(doc["timestamp"]),
                        importance=doc.get("importance", 0.5),
                        metadata={**doc.get("properties", {}), "relevance_score": combined}
                    )
                    results.append((combined, item))
                    seen.add(mem_id)

            except Exception as e:
                logger.warning(f"向量检索失败: {e}")

        # 回退到内存缓存（使用 doc_store 获取完整 metadata）
        if not results:
            query_lower = query.lower()
            now_ts = int(datetime.now().timestamp())
            for ep in self._filter_episodes(user_id, session_id, time_range):
                if query_lower in ep.content.lower():
                    # 从 doc_store 获取完整的 metadata
                    doc = self.doc_store.get_memory(ep.episode_id)
                    if not doc:
                        continue
                    recency_score = 1.0 / (1.0 + max(0.0, (now_ts - int(ep.timestamp.timestamp())) / 86400.0))
                    keyword_score = 0.5
                    base_relevance = keyword_score * 0.8 + recency_score * 0.2
                    importance_weight = 0.8 + (ep.importance * 0.4)
                    combined = base_relevance * importance_weight
                    item = MemoryItem(
                        id=ep.episode_id,
                        content=ep.content,
                        memory_type="episodic",
                        user_id=ep.user_id,
                        timestamp=ep.timestamp,
                        importance=ep.importance,
                        metadata={**doc.get("properties", {})}
                    )
                    results.append((combined, item))

        results.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in results[:limit]]

    def update(self, memory_id: str, content: str = None, importance: float = None, metadata: Dict[str, Any] = None) -> bool:
        updated = False
        for episode in self.episodes:
            if episode.episode_id == memory_id:
                if content is not None:
                    episode.content = content
                if importance is not None:
                    episode.importance = importance
                if metadata is not None:
                    episode.context.update(metadata.get("context", {}))
                    if "outcome" in metadata:
                        episode.outcome = metadata["outcome"]
                updated = True
                break

        doc_updated = self.doc_store.update_memory(memory_id=memory_id, content=content, importance=importance, properties=metadata)

        if content is not None and self.vector_store:
            try:
                embedding = self.embedder.encode(content)
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                doc = self.doc_store.get_memory(memory_id)
                payload = {
                    "memory_id": memory_id,
                    "user_id": doc["user_id"] if doc else "",
                    "memory_type": "episodic",
                    "importance": (doc.get("importance") if doc else importance) or 0.5,
                    "session_id": (doc.get("properties", {}) or {}).get("session_id"),
                    "content": content
                }
                self.vector_store.add_vectors(vectors=[embedding], metadata=[payload], ids=[memory_id])
            except Exception:
                pass

        return updated or doc_updated

    def remove(self, memory_id: str) -> bool:
        removed = False
        for i, episode in enumerate(self.episodes):
            if episode.episode_id == memory_id:
                removed_episode = self.episodes.pop(i)
                session_id = removed_episode.session_id
                if session_id in self.sessions:
                    self.sessions[session_id].remove(memory_id)
                    if not self.sessions[session_id]:
                        del self.sessions[session_id]
                removed = True
                break

        doc_deleted = self.doc_store.delete_memory(memory_id)

        if self.vector_store:
            try:
                self.vector_store.delete_memories([memory_id])
            except Exception:
                pass

        return removed or doc_deleted

    def has_memory(self, memory_id: str) -> bool:
        return any(episode.episode_id == memory_id for episode in self.episodes)

    def clear(self):
        self.episodes.clear()
        self.sessions.clear()

        docs = self.doc_store.search_memories(memory_type="episodic", limit=10000)
        ids = [d["memory_id"] for d in docs]
        for mid in ids:
            self.doc_store.delete_memory(mid)

        if self.vector_store and ids:
            try:
                self.vector_store.delete_memories(ids)
            except Exception:
                pass

    def forget(self, strategy: str = "importance_based", threshold: float = 0.1, max_age_days: int = 30) -> int:
        from datetime import timedelta
        forgotten_count = 0
        current_time = datetime.now()
        to_remove = []

        for episode in self.episodes:
            should_forget = False

            if strategy == "importance_based" and episode.importance < threshold:
                should_forget = True
            elif strategy == "time_based":
                cutoff_time = current_time - timedelta(days=max_age_days)
                if episode.timestamp < cutoff_time:
                    should_forget = True
            elif strategy == "capacity_based":
                if len(self.episodes) > self.config.max_capacity:
                    sorted_episodes = sorted(self.episodes, key=lambda e: e.importance)
                    excess_count = len(self.episodes) - self.config.max_capacity
                    if episode in sorted_episodes[:excess_count]:
                        should_forget = True

            if should_forget:
                to_remove.append(episode.episode_id)

        for episode_id in to_remove:
            if self.remove(episode_id):
                forgotten_count += 1

        return forgotten_count

    def get_all(self) -> List[MemoryItem]:
        memory_items = []
        for episode in self.episodes:
            memory_items.append(MemoryItem(
                id=episode.episode_id,
                content=episode.content,
                memory_type="episodic",
                user_id=episode.user_id,
                timestamp=episode.timestamp,
                importance=episode.importance,
                metadata=episode.context
            ))
        return memory_items

    def get_stats(self) -> Dict[str, Any]:
        db_stats = self.doc_store.get_database_stats()
        vs_stats = {}
        if self.vector_store:
            try:
                vs_stats = self.vector_store.get_collection_stats()
            except Exception:
                pass

        return {
            "count": len(self.episodes),
            "total_count": len(self.episodes),
            "sessions_count": len(self.sessions),
            "avg_importance": sum(e.importance for e in self.episodes) / len(self.episodes) if self.episodes else 0.0,
            "time_span_days": self._calculate_time_span(),
            "memory_type": "episodic",
            "vector_store": vs_stats,
            "document_store": {k: v for k, v in db_stats.items() if k.endswith("_count") or k in ["store_type", "db_path"]}
        }

    def get_session_episodes(self, session_id: str) -> List[Episode]:
        if session_id not in self.sessions:
            return []
        episode_ids = self.sessions[session_id]
        return [e for e in self.episodes if e.episode_id in episode_ids]

    def get_timeline(self, user_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        episodes = [e for e in self.episodes if user_id is None or e.user_id == user_id]
        episodes.sort(key=lambda x: x.timestamp, reverse=True)

        timeline = []
        for episode in episodes[:limit]:
            timeline.append({
                "episode_id": episode.episode_id,
                "timestamp": episode.timestamp.isoformat(),
                "content": episode.content[:100] + "..." if len(episode.content) > 100 else episode.content,
                "session_id": episode.session_id,
                "importance": episode.importance,
                "outcome": episode.outcome
            })

        return timeline

    def _filter_episodes(self, user_id: str = None, session_id: str = None,
                         time_range: Tuple[datetime, datetime] = None) -> List[Episode]:
        filtered = self.episodes

        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]

        if session_id:
            filtered = [e for e in filtered if e.session_id == session_id]

        if time_range:
            start_time, end_time = time_range
            filtered = [e for e in filtered if start_time <= e.timestamp <= end_time]

        return filtered

    def _calculate_time_span(self) -> float:
        if not self.episodes:
            return 0.0
        timestamps = [e.timestamp for e in self.episodes]
        return (max(timestamps) - min(timestamps)).days
