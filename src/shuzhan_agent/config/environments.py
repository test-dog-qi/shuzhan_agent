"""数栈环境配置 - 支持多版本URL路由"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import re


@dataclass
class DataStackEnvironment:
    """数栈环境配置"""
    name: str                           # 环境名称，如 "离线62"
    version: str                        # 版本号，如 "6.2"
    base_url: str                       # 基础URL
    description: str = ""               # 描述
    enabled: bool = True                # 是否启用
    tags: List[str] = field(default_factory=list)  # 标签，用于匹配


# 预定义数栈环境
PREDEFINED_ENVIRONMENTS: List[DataStackEnvironment] = [
    DataStackEnvironment(
        name="离线62测试",
        version="6.2",
        base_url="http://shuzhan62-online-test.k8s.dtstack.cn/",
        description="离线6.2版本测试环境",
        tags=["62", "6.2", "离线", "测试", "shuzhan62"]
    ),
    DataStackEnvironment(
        name="离线63测试",
        version="6.3",
        base_url="http://shuzhan63-online-test.k8s.dtstack.cn/",
        description="离线6.3版本测试环境",
        tags=["63", "6.3", "离线", "测试", "shuzhan63"]
    ),
    DataStackEnvironment(
        name="离线62预发",
        version="6.2",
        base_url="http://shuzhan62-online-pre.k8s.dtstack.cn/",
        description="离线6.2版本预发环境",
        tags=["62", "6.2", "预发", "shuzhan62"]
    ),
    DataStackEnvironment(
        name="离线63预发",
        version="6.3",
        base_url="http://shuzhan63-online-pre.k8s.dtstack.cn/",
        description="离线6.3版本预发环境",
        tags=["63", "6.3", "预发", "shuzhan63"]
    ),
]


class EnvironmentRouter:
    """
    环境路由器 - 根据自然语言意图选择合适的数栈环境

    使用相关性公式计算输入与预定义环境的相似度
    """

    def __init__(self, environments: List[DataStackEnvironment] = None):
        self.environments = environments or PREDEFINED_ENVIRONMENTS

    def route(self, user_input: str) -> Optional[DataStackEnvironment]:
        """
        根据用户输入路由到最合适的环境

        Args:
            user_input: 用户自然语言输入，如"帮我看62环境的任务"

        Returns:
            匹配的环境，如果没有匹配返回None
        """
        # 计算每个环境的相关性得分
        scores = []
        for env in self.environments:
            if not env.enabled:
                continue
            score = self._calculate_relevance(user_input, env)
            scores.append((score, env))

        # 按得分降序排列
        scores.sort(key=lambda x: x[0], reverse=True)

        # 返回得分最高且超过阈值的
        if scores and scores[0][0] > 0.3:
            return scores[0][1]
        return None

    def _calculate_relevance(self, user_input: str, env: DataStackEnvironment) -> float:
        """
        计算用户输入与环境的相关性得分

        使用多维度加权评分：
        1. 版本号匹配 (0-0.4)
        2. 标签词匹配 (0-0.4)
        3. 关键词权重 (0-0.2)
        """
        score = 0.0
        user_lower = user_input.lower()

        # 1. 版本号匹配
        version_patterns = [
            (r'6\.2|62', '6.2'),
            (r'6\.3|63', '6.3'),
            (r'5\.\d', '5.x'),
        ]
        for pattern, version in version_patterns:
            if re.search(pattern, user_lower):
                if env.version == version or version == '5.x' and env.version.startswith('5'):
                    score += 0.4
                break

        # 2. 标签匹配
        matched_tags = 0
        total_tags = len(env.tags)
        for tag in env.tags:
            if tag.lower() in user_lower:
                matched_tags += 1
        if total_tags > 0:
            score += 0.4 * (matched_tags / total_tags)

        # 3. 关键词权重
        keyword_weights = {
            "测试": 0.1,
            "预发": 0.1,
            "生产": 0.1,
            "正式": 0.1,
            "离线": 0.05,
            "实时": 0.05,
            "资产": 0.05,
        }
        for keyword, weight in keyword_weights.items():
            if keyword in user_lower:
                score += weight

        return min(score, 1.0)

    def get_all_environments(self) -> List[DataStackEnvironment]:
        """获取所有可用环境"""
        return [e for e in self.environments if e.enabled]

    def add_environment(self, env: DataStackEnvironment) -> None:
        """添加新环境"""
        self.environments.append(env)

    def match_multiple(self, user_input: str, top_k: int = 3) -> List[Tuple[DataStackEnvironment, float]]:
        """
        返回top_k个最匹配的环境

        Returns:
            [(环境, 得分), ...] 按得分降序
        """
        scores = []
        for env in self.environments:
            if not env.enabled:
                continue
            score = self._calculate_relevance(user_input, env)
            if score > 0:
                scores.append((env, score))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[:top_k]


# 全局路由实例
router = EnvironmentRouter()
