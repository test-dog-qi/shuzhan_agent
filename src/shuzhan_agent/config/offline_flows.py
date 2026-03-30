"""
离线平台流程配置

定义主流程回归测试的执行步骤
API路径已统一在datastack_mcp.py中管理
"""

from typing import Dict, List, Any


# 主流程回归测试的标准步骤
MAIN_FLOW_REGRESSION: List[Dict[str, Any]] = [
    {
        "step_id": "step_1",
        "module": "project",
        "action": "create",
        "name": "创建测试项目",
        "required_params": {
            "projectName": "auto_test_project_{timestamp}",
            "projectAlias": "自动化测试项目",
            "projectOwnerId": "1"
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
            "dataName": "auto_test_datasource",
            "dataDesc": "自动化测试数据源",
            "dataJson": {}
        },
        "depends_on": ["step_1"],
        "expected_result": {"success": True, "datasource_id": "<generated>"}
    },
    {
        "step_id": "step_3",
        "module": "data_development",
        "action": "add_or_update_task",
        "name": "创建数据开发任务",
        "required_params": {
            "taskName": "auto_test_task",
            "taskType": "sql",
            "taskContent": "SELECT 1 AS test"
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


# 执行环境配置模板（已被environments.py替代，仅作向后兼容）
ENVIRONMENT_TEMPLATE: Dict[str, Dict[str, Any]] = {
    "offline_62": {
        "version": "6.2",
        "name": "离线平台62",
        "base_url": "http://shuzhan62-online-test.k8s.dtstack.cn/",
        "timeout": 30,
        "retry_times": 3
    },
    "offline_63": {
        "version": "6.3",
        "name": "离线平台63",
        "base_url": "http://shuzhan63-online-test.k8s.dtstack.cn/",
        "timeout": 30,
        "retry_times": 3
    }
}
