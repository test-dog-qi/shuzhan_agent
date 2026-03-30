"""问题排查Mixin"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class DiagnosisResult:
    """诊断结果"""
    cause: str  # 根本原因
    suggestions: List[str]  # 修复建议
    can_fix: bool  # 是否可以自动修复
    fix_plan: Optional[List[Dict[str, Any]]] = None  # 自动修复计划


class TroubleshooterMixin:
    """
    问题排查Mixin

    提供问题诊断和修复能力：
    1. 收集错误信息
    2. 分析错误原因
    3. 生成修复建议
    4. 执行自动修复（如可能）
    """

    # 错误模式定义
    ERROR_PATTERNS = {
        "connection": {
            "keywords": ["connection", "connect", "连接", "网络"],
            "common_causes": [
                "网络不通",
                "服务不可用",
                "防火墙阻断",
                "连接超时"
            ]
        },
        "authentication": {
            "keywords": ["auth", "token", "unauthorized", "认证", "权限", "permission"],
            "common_causes": [
                "Token过期",
                "权限不足",
                "账号被禁用"
            ]
        },
        "resource_not_found": {
            "keywords": ["not found", "404", "不存在", "未找到"],
            "common_causes": [
                "资源ID错误",
                "资源已被删除",
                "跨环境引用"
            ]
        },
        "resource_conflict": {
            "keywords": ["conflict", "409", "already exists", "重复", "冲突"],
            "common_causes": [
                "资源名称重复",
                "唯一键冲突",
                "状态冲突"
            ]
        },
        "timeout": {
            "keywords": ["timeout", "超时", "timed out"],
            "common_causes": [
                "系统负载高",
                "任务执行时间长",
                "网络延迟"
            ]
        },
        "data_quality": {
            "keywords": ["null", "empty", "数据", "格式", "format"],
            "common_causes": [
                "源数据为空",
                "数据格式不匹配",
                "字段映射错误"
            ]
        }
    }

    def diagnose(self, error: Exception, context: Dict[str, Any]) -> DiagnosisResult:
        """
        诊断错误

        Args:
            error: 异常对象
            context: 执行上下文（包含模块、步骤、参数等信息）

        Returns:
            诊断结果
        """
        error_message = str(error)
        error_type = self._classify_error(error_message)

        # 根据错误类型和上下文生成诊断结果
        if error_type == "connection":
            return self._diagnose_connection_error(error_message, context)
        elif error_type == "authentication":
            return self._diagnose_auth_error(error_message, context)
        elif error_type == "resource_not_found":
            return self._diagnose_not_found_error(error_message, context)
        elif error_type == "resource_conflict":
            return self._diagnose_conflict_error(error_message, context)
        elif error_type == "timeout":
            return self._diagnose_timeout_error(error_message, context)
        else:
            return DiagnosisResult(
                cause="未知错误",
                suggestions=["查看详细错误信息", "联系技术支持"],
                can_fix=False
            )

    def _classify_error(self, error_message: str) -> str:
        """分类错误类型"""
        error_lower = error_message.lower()

        for error_type, pattern in self.ERROR_PATTERNS.items():
            for keyword in pattern["keywords"]:
                if keyword.lower() in error_lower:
                    return error_type

        return "unknown"

    def _diagnose_connection_error(self, error: str, context: Dict[str, Any]) -> DiagnosisResult:
        """诊断连接错误"""
        module = context.get("module", "unknown")

        suggestions = [
            f"检查{module}模块的网络连接",
            "确认目标服务是否正常运行",
            "检查防火墙规则",
            "验证连接超时设置"
        ]

        return DiagnosisResult(
            cause="网络连接失败",
            suggestions=suggestions,
            can_fix=False  # 连接问题通常需要人工介入
        )

    def _diagnose_auth_error(self, error: str, context: Dict[str, Any]) -> DiagnosisResult:
        """诊断认证错误"""
        suggestions = [
            "检查API Token是否有效",
            "确认用户权限是否足够",
            "尝试重新获取认证信息"
        ]

        return DiagnosisResult(
            cause="认证失败或权限不足",
            suggestions=suggestions,
            can_fix=True,
            fix_plan=[
                {"action": "refresh_token", "description": "刷新认证Token"},
                {"action": "check_permission", "description": "检查并申请必要权限"}
            ]
        )

    def _diagnose_not_found_error(self, error: str, context: Dict[str, Any]) -> DiagnosisResult:
        """诊断资源不存在错误"""
        module = context.get("module", "unknown")
        resource_id = context.get("resource_id", "unknown")

        suggestions = [
            f"确认{module}中{resource_id}是否存在",
            "检查资源ID或名称是否正确",
            "可能资源在不同的环境/版本中"
        ]

        return DiagnosisResult(
            cause="请求的资源不存在",
            suggestions=suggestions,
            can_fix=False
        )

    def _diagnose_conflict_error(self, error: str, context: Dict[str, Any]) -> DiagnosisResult:
        """诊断资源冲突错误"""
        resource_name = context.get("resource_name", "unknown")

        suggestions = [
            f"检查{resource_name}是否已存在",
            "使用不同的名称创建资源",
            "先删除已存在的资源"
        ]

        return DiagnosisResult(
            cause="资源冲突，可能已存在同名资源",
            suggestions=suggestions,
            can_fix=True,
            fix_plan=[
                {"action": "query_existing", "description": "查询已存在的同名资源"},
                {"action": "delete_existing", "description": "删除已存在的资源（谨慎使用）"}
            ]
        )

    def _diagnose_timeout_error(self, error: str, context: Dict[str, Any]) -> DiagnosisResult:
        """诊断超时错误"""
        suggestions = [
            "检查目标系统负载情况",
            "增加超时时间重试",
            "将任务拆分为更小的步骤执行"
        ]

        return DiagnosisResult(
            cause="操作超时",
            suggestions=suggestions,
            can_fix=True,
            fix_plan=[
                {"action": "retry_with_longer_timeout", "description": "增加超时时间重试"},
                {"action": "split_task", "description": "拆分任务为更小的步骤"}
            ]
        )

    async def auto_fix(self, diagnosis: DiagnosisResult, context: Dict[str, Any]) -> bool:
        """
        执行自动修复

        Args:
            diagnosis: 诊断结果
            context: 执行上下文

        Returns:
            是否修复成功
        """
        if not diagnosis.can_fix or not diagnosis.fix_plan:
            return False

        # 按计划执行修复
        for step in diagnosis.fix_plan:
            action = step["action"]

            if action == "refresh_token":
                # 刷新Token
                pass
            elif action == "retry_with_longer_timeout":
                # 增加超时重试
                pass

        return False  # 默认返回失败，需要具体实现
