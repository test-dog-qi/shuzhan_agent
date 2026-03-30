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
        """构建API路径 - 基于dtstack-httprunner真实API"""
        api_paths = {
            # 项目管理 - /api/rdos/common/project/
            ("project", "create"): "/api/rdos/common/project/createProject",
            ("project", "delete"): "/api/rdos/common/project/deleteProject",
            ("project", "get_projects"): "/api/rdos/common/project/getProjects",
            ("project", "get_by_id"): "/api/rdos/common/project/getProjectByProjectId",
            ("project", "get_info"): "/api/rdos/common/project/getProjectInfo",
            ("project", "update_info"): "/api/rdos/common/project/updateProjectInfo",
            ("project", "pre_delete"): "/api/rdos/common/project/preDeleteProject",
            ("project", "get_support_engine_type"): "/api/rdos/common/project/getSupportEngineType",
            ("project", "get_project_engine_info"): "/api/rdos/common/project/getProjectEngineInfo",
            ("project", "get_project_users"): "/api/rdos/common/project/getProjectUsers",

            # 数据源 - /api/rdos/batch/batchDataSource/
            ("datasource", "list"): "/api/rdos/batch/batchDataSource/list",
            ("datasource", "get_types"): "/api/rdos/batch/batchDataSource/getTypes",
            ("datasource", "get_by_id"): "/api/rdos/batch/batchDataSource/getBySourceId",
            ("datasource", "preview"): "/api/rdos/batch/batchDataSource/preview",
            ("datasource", "get_tables_by_ds"): "/api/rdos/batch/batchDataSource/getTableInfoByDataSource",

            # 数据开发-任务 - /api/rdos/batch/batchTask/
            ("data_development", "get_task_by_id"): "/api/rdos/batch/batchTask/getTaskById",
            ("data_development", "add_or_update_task"): "/api/rdos/batch/batchTask/addOrUpdateTask",
            ("data_development", "delete_task"): "/api/rdos/batch/batchTask/deleteTask",
            ("data_development", "query_tasks"): "/api/rdos/batch/batchTask/queryTasks",
            ("data_development", "get_tasks_by_project"): "/api/rdos/batch/batchTask/getTasksByProjectId",
            ("data_development", "publish_task"): "/api/rdos/batch/batchTask/publishTask",
            ("data_development", "run_task"): "/api/rdos/batch/batchTask/startSqlImmediately",
            ("data_development", "frozen_task"): "/api/rdos/batch/batchTask/frozenTask",
            ("data_development", "rename_task"): "/api/rdos/batch/batchTask/renameTask",
            ("data_development", "clone_task"): "/api/rdos/batch/batchTask/cloneTask",

            # 运维中心-作业 - /api/rdos/batch/batchJob/
            ("ops_center", "get_job_by_id"): "/api/rdos/batch/batchJob/getJobById",
            ("ops_center", "get_job_status"): "/api/rdos/batch/batchJob/getJobStatus",
            ("ops_center", "get_status_count"): "/api/rdos/batch/batchJob/getStatusCount",
            ("ops_center", "query_jobs"): "/api/rdos/batch/batchJob/queryJobs",
            ("ops_center", "run_job"): "/api/rdos/batch/batchJob/startSqlImmediately",
            ("ops_center", "stop_job"): "/api/rdos/batch/batchJob/stopJob",
            ("ops_center", "re_run"): "/api/rdos/batch/batchJob/restartJobAndResume",
            ("ops_center", "fill_data"): "/api/rdos/batch/batchJob/fillTaskData",
            ("ops_center", "create_fill_data"): "/api/rdos/batch/fillData/createFillData",
            ("ops_center", "get_related_jobs"): "/api/rdos/batch/batchJob/getRelatedJobs",
            ("ops_center", "get_fill_data_detail"): "/api/rdos/batch/batchJob/getFillDataDetailInfo",

            # 数据地图 - /api/rdos/batch/batchTableInfo/
            ("data_map", "page_query"): "/api/rdos/batch/batchTableInfo/pageQuery",
            ("data_map", "get_table"): "/api/rdos/batch/batchTableInfo/getTable",
            ("data_map", "get_table_by_name"): "/api/rdos/batch/batchTableInfo/getTableByName",
            ("data_map", "get_table_columns"): "/api/rdos/batch/batchTableInfo/getTableColumnsByName",
            ("data_map", "get_table_list"): "/api/rdos/batch/batchTableInfo/getTableList",
            ("data_map", "get_blood_tree"): "/api/rdos/batch/batchTableBlood/getTree",
            ("data_map", "get_blood_columns"): "/api/rdos/batch/batchTableBlood/getColumns",

            # 脚本 - /api/rdos/batch/batchScript/
            ("script", "get_types"): "/api/rdos/batch/batchScript/getTypes",
            ("script", "add_or_update"): "/api/rdos/batch/batchScript/addOrUpdateScript",
            ("script", "delete"): "/api/rdos/batch/batchScript/deleteScript",
            ("script", "get_by_id"): "/api/rdos/batch/batchScript/getScriptById",
        }

        return api_paths.get((module, action), f"/api/rdos/batch/{module}/{action}")

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
        """获取支持的工具列表 - 基于真实API"""
        return [
            # 项目管理
            {"name": "create_project", "description": "创建项目", "params": {"projectName": "str", "projectAlias": "str", "projectOwnerId": "str"}},
            {"name": "delete_project", "description": "删除项目", "params": {"projectAlias": "str", "projectId": "str"}},
            {"name": "get_projects", "description": "获取租户下所有项目", "params": {}},
            {"name": "get_project_by_id", "description": "根据ID获取项目详情", "params": {"projectId": "str"}},
            {"name": "update_project_info", "description": "更新项目信息", "params": {"projectAlias": "str", "projectDesc": "str", "projectId": "str"}},
            {"name": "get_project_users", "description": "获取项目下用户列表", "params": {"projectId": "str"}},

            # 数据源
            {"name": "list_datasources", "description": "获取数据源列表", "params": {"currentPage": "int", "pageSize": "int", "search": "str"}},
            {"name": "get_datasource_types", "description": "获取支持的数据源类型", "params": {}},
            {"name": "preview_datasource", "description": "预览数据源数据", "params": {"sourceId": "str"}},

            # 数据开发
            {"name": "get_task_by_id", "description": "根据ID获取任务", "params": {"taskId": "str"}},
            {"name": "add_or_update_task", "description": "创建或更新任务", "params": {"task": "dict"}},
            {"name": "delete_task", "description": "删除任务", "params": {"taskId": "str"}},
            {"name": "query_tasks", "description": "查询任务列表", "params": {}},
            {"name": "get_tasks_by_project", "description": "获取项目下所有任务", "params": {"projectId": "str"}},
            {"name": "publish_task", "description": "发布任务", "params": {"taskId": "str"}},
            {"name": "run_task", "description": "立即运行任务(SQL)", "params": {"taskId": "str"}},
            {"name": "frozen_task", "description": "冻结任务", "params": {"taskId": "str"}},

            # 运维中心
            {"name": "get_job_by_id", "description": "获取作业详情", "params": {"id": "str"}},
            {"name": "get_job_status", "description": "获取作业状态", "params": {"id": "str"}},
            {"name": "query_jobs", "description": "查询作业列表", "params": {}},
            {"name": "run_job", "description": "立即运行作业", "params": {"id": "str"}},
            {"name": "stop_job", "description": "停止作业", "params": {"id": "str"}},
            {"name": "re_run_job", "description": "重跑作业", "params": {"id": "str"}},
            {"name": "fill_data", "description": "补数据", "params": {"taskId": "str", "startDate": "str", "endDate": "str"}},
            {"name": "get_related_jobs", "description": "获取相关作业", "params": {"id": "str"}},

            # 数据地图
            {"name": "page_query_tables", "description": "分页查询表", "params": {"currentPage": "int", "pageSize": "int"}},
            {"name": "get_table", "description": "获取表详情", "params": {"tableId": "str"}},
            {"name": "get_table_by_name", "description": "根据名称获取表", "params": {"projectId": "str", "tableName": "str"}},
            {"name": "get_blood_tree", "description": "获取血缘关系树", "params": {"tableId": "str"}},

            # 脚本
            {"name": "get_script_types", "description": "获取脚本类型", "params": {}},
            {"name": "add_or_update_script", "description": "创建或更新脚本", "params": {"script": "dict"}},
            {"name": "get_script_by_id", "description": "获取脚本详情", "params": {"id": "str"}},
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
