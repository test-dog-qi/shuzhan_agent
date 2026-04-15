"""统一嵌入模块 - text-embedding-v4 为主，sentence-transformers 兜底"""

import os
import threading
from typing import List, Union, Optional
import numpy as np

# 优先尝试 sentence-transformers（用于获取维度信息）
try:
    import numpy
    if numpy.__version__.startswith("2."):
        raise ImportError("NumPy 2.x not supported")
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except (ImportError, Exception):
    ST_AVAILABLE = False


class EmbedderBase:
    """嵌入模型基类"""

    def encode(self, texts: Union[str, List[str]]):
        raise NotImplementedError

    @property
    def dimension(self) -> int:
        raise NotImplementedError


class TextEmbeddingV4(EmbedderBase):
    """阿里云 DashScope text-embedding-v4 嵌入模型

    使用 OpenAI 兼容的 REST API 调用
    """

    def __init__(self, model_name: str = "text-embedding-v4", api_key: str = None, base_url: str = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("EMBED_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("EMBED_BASE_URL") or os.getenv("DASHSCOPE_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

        if not self.api_key:
            raise ValueError("需要设置 EMBED_API_KEY 环境变量")

        self._dimension = None
        self._init_client()

    def _init_client(self):
        import httpx
        self._client = httpx.Client(timeout=30)

        # 先探测维度
        test_vec = self.encode("health_check")
        self._dimension = len(test_vec)

    def encode(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        import httpx

        if isinstance(texts, str):
            inputs = [texts]
            single = True
        else:
            inputs = list(texts)
            single = False

        url = f"{self.base_url.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"model": self.model_name, "input": inputs}

        try:
            response = self._client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            items = data.get("data", [])
            if not items:
                raise RuntimeError("Embedding 返回为空")

            # 提取向量
            vecs = []
            for item in items:
                emb = item.get("embedding", [])
                vecs.append(np.array(emb, dtype=np.float32))

            if single:
                return vecs[0].tolist()
            return [v.tolist() for v in vecs]

        except Exception as e:
            raise RuntimeError(f"Embedding 调用失败: {e}")

    @property
    def dimension(self) -> int:
        return int(self._dimension or 0)


class SentenceTransformerEmbedder(EmbedderBase):
    """Sentence-Transformers 本地嵌入（兜底方案）"""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        if not ST_AVAILABLE:
            raise ImportError("sentence-transformers 不可用")

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()

    def encode(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        if isinstance(texts, str):
            single = True
            texts = [texts]
        else:
            single = False

        vecs = self._model.encode(texts, convert_to_numpy=True)

        if single:
            return vecs[0].tolist()
        return vecs.tolist()

    @property
    def dimension(self) -> int:
        return int(self._dimension or 384)


# ==============
# 单例管理
# ==============

_lock = threading.RLock()
_embedder: Optional[EmbedderBase] = None


def _build_embedder() -> EmbedderBase:
    """构建嵌入器：优先 text-embedding-v4，失败则 sentence-transformers"""

    # 1. 优先尝试 text-embedding-v4
    api_key = os.getenv("EMBED_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("EMBED_BASE_URL") or os.getenv("DASHSCOPE_BASE_URL") or os.getenv("OPENAI_BASE_URL")

    if api_key:
        try:
            embedder = TextEmbeddingV4(
                api_key=api_key,
                base_url=base_url
            )
            return embedder
        except Exception as e:
            print(f"⚠️ text-embedding-v4 初始化失败: {e}，将使用 sentence-transformers 兜底")

    # 2. sentence-transformers 兜底
    if ST_AVAILABLE:
        try:
            model_name = os.getenv("EMBED_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
            embedder = SentenceTransformerEmbedder(model_name=model_name)
            return embedder
        except Exception as e:
            print(f"⚠️ sentence-transformers 初始化失败: {e}")

    raise RuntimeError("无法初始化任何嵌入模型，请安装 sentence-transformers 或配置 EMBED_API_KEY")


def get_embedder() -> EmbedderBase:
    """获取全局嵌入器实例（线程安全单例）"""
    global _embedder
    if _embedder is not None:
        return _embedder
    with _lock:
        if _embedder is None:
            _embedder = _build_embedder()
        return _embedder


def get_dimension(default: int = 384) -> int:
    """获取统一向量维度"""
    try:
        return int(getattr(get_embedder(), "dimension", default))
    except Exception:
        return int(default)


def refresh_embedder() -> EmbedderBase:
    """强制重建嵌入器实例"""
    global _embedder
    with _lock:
        _embedder = _build_embedder()
        return _embedder
