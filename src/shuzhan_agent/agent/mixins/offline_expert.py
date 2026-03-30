"""离线平台专家Mixin"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from ..mcp.datastack_mcp import OFFLINE_MODULES, MODULE_DEPENDENCIES


@dataclass
class ModuleFlow:
    """模块流程定义"""
    module: str
    flow_name: str
    description: str
    required_params: Dict[str, Any]
    optional_params: Dict[str, Any] = None
    depends_on: List[str] = None  # 依赖的flow名称


class OfflineExpertMixin:
    """
    离线平台专家Mixin

    包含离线平台各模块的专业知识：
    1. 模块间的依赖关系
    2. 各模块的API调用方式
    3. 业务流程和最佳实践
    4. 常见问题诊断
    """

    # 主流程回归测试的标准流程
    MAIN_FLOW_STEPS = [
        ModuleFlow(
            module="project",
            flow_name="create_project",
            description="创建测试项目",
            required_params={"name": "测试项目名称", "desc": "项目描述"},
        ),
        ModuleFlow(
            module="datasource",
            flow_name="create_datasource",
            description="创建测试数据源",
            required_params={"type": "数据源类型", "name": "数据源名称", "config": "连接配置"},
            depends_on=["create_project"]
        ),
        ModuleFlow(
            module="data_development",
            flow_name="create_task",
            description="创建数据开发任务",
            required_params={"project_id": "项目ID", "type": "任务类型", "name": "任务名称", "script": "脚本内容"},
            depends_on=["create_project", "create_datasource"]
        ),
        ModuleFlow(
            module="data_development",
            flow_name="run_task",
            description="运行数据开发任务",
            required_params={"task_id": "任务ID"},
            depends_on=["create_task"]
        ),
        ModuleFlow(
            module="ops_center",
            flow_name="check_job_status",
            description="检查作业运行状态",
            required_params={"job_id": "作业ID"},
            depends_on=["run_task"]
        ),
        ModuleFlow(
            module="data_map",
            flow_name="verify_table",
            description="验证数据地图中的表",
            required_params={"table_name": "表名"},
            depends_on=["run_task"]
        ),
    ]

    def understand_intent(self, user_input: str) -> Dict[str, Any]:
        """
        理解用户意图

        Args:
            user_input: 用户输入的自然语言指令

        Returns:
            解析后的意图结构
        """
        # 这里可以通过LLM来理解意图，也可以用规则匹配
        intent = {
            "action": None,
            "environment": None,
            "scope": None,
            "params": {}
        }

        # 简单规则匹配 - 实际应该用LLM
        user_lower = user_input.lower()

        if "构造" in user_input or "创建" in user_input or "造数" in user_input:
            intent["action"] = "create_test_data"
        elif "验证" in user_input or "检查" in user_input:
            intent["action"] = "verify"
        elif "主流程" in user_input or "回归" in user_input:
            intent["action"] = "main_flow_regression"
            intent["scope"] = "all"
        elif "清理" in user_input or "删除" in user_input:
            intent["action"] = "cleanup"

        # 解析环境版本
        if "62" in user_input or "6.2" in user_input:
            intent["environment"] = {"version": "6.2", "name": "离线平台62"}
        elif "63" in user_input or "6.3" in user_input:
            intent["environment"] = {"version": "6.3", "name": "离线平台63"}

        return intent

    def generate_execution_plan(self, intent: Dict[str, Any]) -> List[ModuleFlow]:
        """
        根据意图生成执行计划

        Args:
            intent: 解析后的意图

        Returns:
            执行步骤列表
        """
        action = intent.get("action")

        if action == "main_flow_regression":
            # 主流程回归测试 - 返回标准流程
            return self.MAIN_FLOW_STEPS
        elif action == "create_test_data":
            # 创建测试数据 - 根据范围确定步骤
            scope = intent.get("scope", "all")
            if scope == "all":
                return self.MAIN_FLOW_STEPS
            # 可以根据需要返回特定模块的流程
        elif action == "verify":
            # 验证流程
            return [
                ModuleFlow(
                    module="project",
                    flow_name="query_projects",
                    description="查询项目",
                    required_params={}
                ),
                ModuleFlow(
                    module="ops_center",
                    flow_name="check_job_status",
                    description="检查作业状态",
                    required_params={},
                    depends_on=["query_projects"]
                ),
            ]

        return []

    def get_module_dependencies(self, module: str) -> List[str]:
        """获取模块依赖"""
        return MODULE_DEPENDENCIES.get(module, [])

    def get_module_info(self, module: str) -> Optional[Dict[str, Any]]:
        """获取模块信息"""
        return OFFLINE_MODULES.get(module)

    def validate_params(self, flow: ModuleFlow, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证参数是否满足要求

        Returns:
            (是否有效, 错误信息)
        """
        for required_param in flow.required_params:
            if required_param not in params:
                return False, f"缺少必需参数: {required_param}"

        return True, None

    def suggest_fix(self, flow: ModuleFlow, error: str) -> List[str]:
        """
        根据错误建议修复方案

        Args:
            flow: 流程定义
            error: 错误信息

        Returns:
            修复建议列表
        """
        suggestions = []

        # 常见错误和修复建议
        if "connection" in error.lower() or "连接" in error:
            suggestions.append("检查数据源配置是否正确")
            suggestions.append("确认网络连接是否正常")
            suggestions.append("验证账号密码是否有效")

        if "permission" in error.lower() or "权限" in error:
            suggestions.append("检查用户是否有所需权限")
            suggestions.append("尝试联系管理员开通权限")

        if "not found" in error.lower() or "不存在" in error:
            suggestions.append("确认资源是否已创建")
            suggestions.append("检查ID或名称是否正确")

        if "timeout" in error.lower() or "超时" in error:
            suggestions.append("检查目标系统是否负载过高")
            suggestions.append("适当增加超时时间")

        return suggestions
