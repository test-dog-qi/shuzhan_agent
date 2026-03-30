"""数栈平台MCP Server"""

import httpx
from typing import Any, Dict, List, Optional

from .base import MCPServer


class DataStackMCP(MCPServer):
    """
    数栈平台MCP Server

    提供数栈离线平台各模块的API调用能力

    支持的模块：
    - project: 项目管理
    - datasource: 数据源
    - data_development: 数据开发
    - ops_center: 运维中心
    - data_map: 数据地图
    """

    def __init__(
        self,
        base_url: str,
        api_token: Optional[str] = None,
        timeout: int = 30,
    ):
        super().__init__(
            name="datastack_mcp",
            description="数栈平台API调用"
        )
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None:
            headers = {}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout
            )
        return self._client

    async def execute(self, module: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行数栈API调用

        Args:
            module: 模块名 (project/datasource/data_development/ops_center/data_map)
            action: 操作名 (create/update/delete/query/run/...)
            params: 参数

        Returns:
            API响应结果
        """
        # 根据module和action构建API路径
        api_path = self._build_api_path(module, action)

        # 提取HTTP方法
        method = self._get_http_method(action)

        # 执行请求
        client = await self._get_client()

        try:
            response = await client.request(
                method=method,
                url=api_path,
                json=params if method in ["POST", "PUT", "PATCH"] else None,
                params=params if method in ["GET", "DELETE"] else None,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "data": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "data": None
            }

    def _build_api_path(self, module: str, action: str) -> str:
        """构建API路径"""
        # 这里需要根据数栈的实际API来定义
        api_paths = {
            # 项目管理
            ("project", "create"): "/api/projects",
            ("project", "update"): "/api/projects/{id}",
            ("project", "delete"): "/api/projects/{id}",
            ("project", "query"): "/api/projects",
            ("project", "get"): "/api/projects/{id}",

            # 数据源
            ("datasource", "create"): "/api/datasources",
            ("datasource", "update"): "/api/datasources/{id}",
            ("datasource", "delete"): "/api/datasources/{id}",
            ("datasource", "query"): "/api/datasources",
            ("datasource", "test"): "/api/datasources/test",

            # 数据开发
            ("data_development", "create_task"): "/api/tasks",
            ("data_development", "update_task"): "/api/tasks/{id}",
            ("data_development", "delete_task"): "/api/tasks/{id}",
            ("data_development", "query_tasks"): "/api/tasks",
            ("data_development", "get_task"): "/api/tasks/{id}",
            ("data_development", "run_task"): "/api/tasks/{id}/run",

            # 运维中心
            ("ops_center", "query_jobs"): "/api/jobs",
            ("ops_center", "get_job"): "/api/jobs/{id}",
            ("ops_center", "run_job"): "/api/jobs/{id}/run",
            ("ops_center", "stop_job"): "/api/jobs/{id}/stop",
            ("ops_center", "re_run"): "/api/jobs/{id}/re-run",
            ("ops_center", "fill_data"): "/api/jobs/{id}/fill-data",

            # 数据地图
            ("data_map", "query_tables"): "/api/tables",
            ("data_map", "get_table"): "/api/tables/{id}",
            ("data_map", "query_lineage"): "/api/tables/{id}/lineage",
            ("data_map", "apply_permission"): "/api/tables/{id}/permission",
        }

        return api_paths.get((module, action), f"/api/{module}/{action}")

    def _get_http_method(self, action: str) -> str:
        """根据操作名确定HTTP方法"""
        if action.startswith("create") or action.startswith("run") or action == "test":
            return "POST"
        elif action.startswith("update") or action.startswith("apply"):
            return "PUT"
        elif action.startswith("delete"):
            return "DELETE"
        else:
            return "GET"

    def get_tools(self) -> List[Dict[str, Any]]:
        """获取支持的工具列表"""
        return [
            # 项目管理
            {"name": "create_project", "description": "创建项目", "params": {"name": "str", "desc": "str"}},
            {"name": "update_project", "description": "更新项目", "params": {"id": "str", "name": "str", "desc": "str"}},
            {"name": "delete_project", "description": "删除项目", "params": {"id": "str"}},
            {"name": "query_projects", "description": "查询项目列表", "params": {}},
            {"name": "get_project", "description": "获取项目详情", "params": {"id": "str"}},

            # 数据源
            {"name": "create_datasource", "description": "创建数据源", "params": {"type": "str", "name": "str", "config": "dict"}},
            {"name": "test_datasource", "description": "测试数据源连接", "params": {"id": "str"}},
            {"name": "query_datasources", "description": "查询数据源列表", "params": {}},

            # 数据开发
            {"name": "create_task", "description": "创建数据开发任务", "params": {"project_id": "str", "type": "str", "name": "str", "script": "str"}},
            {"name": "run_task", "description": "运行任务", "params": {"id": "str"}},

            # 运维中心
            {"name": "run_job", "description": "运行作业", "params": {"id": "str"}},
            {"name": "re_run_job", "description": "重跑作业", "params": {"id": "str"}},
            {"name": "fill_data_job", "description": "补数作业", "params": {"id": "str", "start_date": "str", "end_date": "str"}},

            # 数据地图
            {"name": "query_tables", "description": "查询表列表", "params": {}},
            {"name": "query_lineage", "description": "查询表血缘", "params": {"table_id": "str"}},
        ]


# 离线平台模块定义
OFFLINE_MODULES = {
    "project": {
        "name": "项目管理",
        "description": "项目的创建、管理、成员和角色权限",
        "flows": ["create", "update", "delete", "query"]
    },
    "datasource": {
        "name": "数据源",
        "description": "各种数据源的连接配置和管理",
        "flows": ["create", "update", "delete", "query", "test"]
    },
    "data_development": {
        "name": "数据开发",
        "description": "SQL任务、Python任务、Shell任务的创建和调度",
        "flows": ["create_task", "update_task", "delete_task", "query_tasks", "run_task"]
    },
    "ops_center": {
        "name": "运维中心",
        "description": "任务监控、周期调度、补数操作、重跑机制",
        "flows": ["query_jobs", "run_job", "stop_job", "re_run", "fill_data"]
    },
    "data_map": {
        "name": "数据地图",
        "description": "表管理、血缘关系、权限申请",
        "flows": ["query_tables", "get_table", "query_lineage", "apply_permission"]
    }
}


# 依赖关系定义
MODULE_DEPENDENCIES = {
    "project": [],  # 项目是基础，无依赖
    "datasource": ["project"],  # 数据源依赖项目
    "data_development": ["project", "datasource"],  # 数据开发依赖项目和数据源
    "ops_center": ["project", "data_development"],  # 运维中心依赖项目和数据开发
    "data_map": ["project", "datasource"],  # 数据地图依赖项目和数据源
}
