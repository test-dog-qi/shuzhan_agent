"""Qdrant向量数据库存储实现"""

import logging
import os
import uuid
import threading
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    models = None


class QdrantConnectionManager:
    """Qdrant连接管理器 - 单例模式"""
    _instances = {}
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, url: str = None, api_key: str = None, collection_name: str = "shuzhan_agent_vectors",
                     vector_size: int = 384, distance: str = "cosine", timeout: int = 30, **kwargs):
        key = (url or "local", collection_name)

        if key not in cls._instances:
            with cls._lock:
                if key not in cls._instances:
                    cls._instances[key] = QdrantVectorStore(
                        url=url, api_key=api_key, collection_name=collection_name,
                        vector_size=vector_size, distance=distance, timeout=timeout, **kwargs
                    )

        return cls._instances[key]


class QdrantVectorStore:
    """Qdrant向量数据库存储实现"""

    def __init__(self, url: str = None, api_key: str = None, collection_name: str = "shuzhan_agent_vectors",
                 vector_size: int = 384, distance: str = "cosine", timeout: int = 30, **kwargs):
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client未安装。请运行: pip install qdrant-client>=1.6.0")

        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.timeout = timeout

        distance_map = {"cosine": Distance.COSINE, "dot": Distance.DOT, "euclidean": Distance.EUCLID}
        self.distance = distance_map.get(distance.lower(), Distance.COSINE)

        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            if self.url and self.api_key:
                self.client = QdrantClient(url=self.url, api_key=self.api_key, timeout=self.timeout)
                logger.info(f"已连接到Qdrant云服务: {self.url}")
            elif self.url:
                self.client = QdrantClient(url=self.url, timeout=self.timeout)
                logger.info(f"已连接到Qdrant服务: {self.url}")
            else:
                self.client = QdrantClient(host="localhost", port=6333, timeout=self.timeout)
                logger.info("已连接到本地Qdrant服务: localhost:6333")

            self._ensure_collection()

        except Exception as e:
            logger.error(f"Qdrant连接失败: {e}")
            raise

    def _ensure_collection(self):
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=self.distance)
                )
                logger.info(f"已创建Qdrant集合: {self.collection_name}")
            else:
                # 检查现有集合的向量维度是否匹配
                try:
                    collection_info = self.client.get_collection(self.collection_name)
                    # 获取配置中的向量维度
                    vectors_config = getattr(collection_info, 'vectors_config', None)
                    if vectors_config:
                        existing_size = getattr(vectors_config, 'size', None)
                        if existing_size and existing_size != self.vector_size:
                            logger.warning(
                                f"向量维度不匹配: 集合={existing_size}, 配置={self.vector_size}，"
                                f"将删除旧集合并创建新集合"
                            )
                            self.client.delete_collection(collection_name=self.collection_name)
                            self.client.create_collection(
                                collection_name=self.collection_name,
                                vectors_config=VectorParams(size=self.vector_size, distance=self.distance)
                            )
                            logger.info(f"已重建Qdrant集合: {self.collection_name}")
                        else:
                            logger.info(f"使用现有Qdrant集合: {self.collection_name} (维度匹配)")
                    else:
                        logger.info(f"使用现有Qdrant集合: {self.collection_name}")
                except Exception as e:
                    logger.warning(f"检查集合维度失败: {e}，使用现有集合")

            self._ensure_payload_indexes()

        except Exception as e:
            logger.error(f"集合初始化失败: {e}")
            raise

    def _ensure_payload_indexes(self):
        try:
            index_fields = [
                ("memory_type", models.PayloadSchemaType.KEYWORD),
                ("user_id", models.PayloadSchemaType.KEYWORD),
                ("memory_id", models.PayloadSchemaType.KEYWORD),
                ("timestamp", models.PayloadSchemaType.INTEGER)
            ]
            for field_name, schema_type in index_fields:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=schema_type
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"创建payload索引时出错: {e}")

    def add_vectors(self, vectors: List[List[float]], metadata: List[Dict[str, Any]],
                    ids: Optional[List[str]] = None) -> bool:
        try:
            if not vectors:
                return False

            if ids is None:
                ids = [f"vec_{i}_{int(uuid.uuid4().time * 1000000)}" for i in range(len(vectors))]

            points = []
            for vector, meta, point_id in zip(vectors, metadata, ids):
                if len(vector) != self.vector_size:
                    continue

                meta_with_timestamp = meta.copy()
                meta_with_timestamp["timestamp"] = int(uuid.uuid4().time)

                safe_id = point_id
                if isinstance(point_id, str):
                    try:
                        uuid.UUID(point_id)
                        safe_id = point_id
                    except Exception:
                        safe_id = str(uuid.uuid4())

                point = PointStruct(id=safe_id, vector=vector, payload=meta_with_timestamp)
                points.append(point)

            if not points:
                return False

            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
            return True

        except Exception as e:
            logger.error(f"添加向量失败: {e}")
            return False

    def search_similar(self, query_vector: List[float], limit: int = 10,
                      score_threshold: float = None, where: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        try:
            if len(query_vector) != self.vector_size:
                logger.error(f"查询向量维度错误: 期望{self.vector_size}, 实际{len(query_vector)}")
                return []

            query_filter = None
            if where:
                conditions = []
                for key, value in where.items():
                    if isinstance(value, (str, int, float, bool)):
                        conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                if conditions:
                    query_filter = Filter(must=conditions)

            search_result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )

            results = []
            for hit in search_result.points:
                results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "metadata": hit.payload or {}
                })

            return results

        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []

    def delete_memories(self, memory_ids: List[str]):
        try:
            if not memory_ids:
                return
            conditions = [FieldCondition(key="memory_id", match=MatchValue(value=mid)) for mid in memory_ids]
            query_filter = Filter(should=conditions)
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=query_filter),
                wait=True
            )
        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            raise

    def get_collection_stats(self) -> Dict[str, Any]:
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": collection_info.points_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "store_type": "qdrant"
            }
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {"store_type": "qdrant", "name": self.collection_name}

    def health_check(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def __del__(self):
        if hasattr(self, 'client') and self.client:
            try:
                self.client.close()
            except:
                pass
