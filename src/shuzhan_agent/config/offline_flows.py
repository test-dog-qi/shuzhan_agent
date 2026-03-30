"""离线平台流程配置"""

from typing import Dict, List, Any


# 离线平台模块定义
OFFLINE_MODULES_CONFIG = {
    "project": {
        "name": "项目管理",
        "description": "项目的创建、管理、成员和角色权限",
        "api_base": "/api/projects",
        "key_fields": ["id", "name", "description", "owner", "create_time"]
    },
    "datasource": {
        "name": "数据源",
        "description": "各种数据源的连接配置和管理",
        "api_base": "/api/datasources",
        "key_fields": ["id", "name", "type", "connection_config"],
        "supported_types": [
            "mysql", "postgresql", "oracle", "sqlserver",
            "hive", "hdfs", "kafka", "hbase", "elasticsearch"
        ]
    },
    "data_development": {
        "name": "数据开发",
        "description": "SQL任务、Python任务、Shell任务的创建和调度",
        "api_base": "/api/tasks",
        "key_fields": ["id", "name", "type", "script", "schedule"],
        "task_types": ["sql", "python", "shell", "spark", "flink"]
    },
    "ops_center": {
        "name": "运维中心",
        "description": "任务监控、周期调度、补数操作、重跑机制",
        "api_base": "/api/jobs",
        "key_fields": ["id", "name", "status", "start_time", "end_time"],
        "job_status": ["wait", "running", "success", "failed", "stopped"]
    },
    "data_map": {
        "name": "数据地图",
        "description": "表管理、血缘关系、权限申请",
        "api_base": "/api/tables",
        "key_fields": ["id", "name", "database", "table_type", "lineage"]
    }
}


# 依赖关系定义
MODULE_DEPENDENCIES_CONFIG = {
    "project": [],  # 项目是基础，无依赖
    "datasource": ["project"],  # 数据源依赖项目
    "data_development": ["project", "datasource"],  # 数据开发依赖项目和数据源
    "ops_center": ["project", "data_development"],  # 运维中心依赖项目和数据开发
    "data_map": ["project", "datasource"],  # 数据地图依赖项目和数据源
}


# 主流程回归测试的标准步骤
MAIN_FLOW_REGRESSION = [
    {
        "step_id": "step_1",
        "module": "project",
        "action": "create",
        "name": "创建测试项目",
        "required_params": {
            "name": "auto_test_project_{timestamp}",
            "desc": "自动化主流程回归测试项目"
        },
        "expected_result": {"success": True, "project_id": "<generated>"}
    },
    {
        "step_id": "step_2",
        "module": "datasource",
        "action": "create",
        "name": "创建测试数据源",
        "required_params": {
            "type": "mysql",
            "name": "auto_test_datasource",
            "config": {}
        },
        "depends_on": ["step_1"],
        "expected_result": {"success": True, "datasource_id": "<generated>"}
    },
    {
        "step_id": "step_3",
        "module": "data_development",
        "action": "create_task",
        "name": "创建数据开发任务",
        "required_params": {
            "type": "sql",
            "name": "auto_test_task",
            "script": "SELECT 1 AS test"
        },
        "depends_on": ["step_1", "step_2"],
        "expected_result": {"success": True, "task_id": "<generated>"}
    },
    {
        "step_id": "step_4",
        "module": "data_development",
        "action": "run_task",
        "name": "运行数据开发任务",
        "required_params": {},
        "depends_on": ["step_3"],
        "expected_result": {"success": True, "job_id": "<generated>"}
    },
    {
        "step_id": "step_5",
        "module": "ops_center",
        "action": "check_status",
        "name": "检查作业状态",
        "required_params": {},
        "depends_on": ["step_4"],
        "expected_result": {"status": "success"}
    },
    {
        "step_id": "step_6",
        "module": "data_map",
        "action": "verify_table",
        "name": "验证数据地图",
        "required_params": {},
        "depends_on": ["step_4"],
        "expected_result": {"table_exists": True}
    }
]


# 执行环境配置模板
ENVIRONMENT_TEMPLATE = {
    "offline_62": {
        "version": "6.2",
        "name": "离线平台62",
        "base_url": "http://datastack-offline-62.example.com",
        "timeout": 30,
        "retry_times": 3
    },
    "offline_63": {
        "version": "6.3",
        "name": "离线平台63",
        "base_url": "http://datastack-offline-63.example.com",
        "timeout": 30,
        "retry_times": 3
    }
}
