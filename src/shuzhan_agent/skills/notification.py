"""
通知技能 - 封装MCP调用

实际HTTP请求由http-mcp处理，这里只保留业务逻辑
"""

from typing import Any, Dict, Optional, List
from dataclasses import dataclass


@dataclass
class NotificationMessage:
    """通知消息"""
    channel: str
    message: str
    msg_type: str = "text"


class NotificationSkill:
    """
    通知技能

    封装MCP调用，发送飞书/钉钉通知
    """

    def __init__(self):
        self.channels: Dict[str, Dict[str, str]] = {}
        self._mcp_tools: Optional[Any] = None

    def set_mcp_tools(self, mcp_tools: Any) -> None:
        """设置MCP工具集（由Agent在运行时注入）"""
        self._mcp_tools = mcp_tools

    def add_channel(self, name: str, channel_type: str, webhook_url: str, **kwargs):
        """
        添加通知渠道

        Args:
            name: 渠道名称
            channel_type: 渠道类型 (feishu/dingtalk)
            webhook_url: Webhook地址
        """
        self.channels[name] = {
            "type": channel_type,
            "webhook_url": webhook_url,
            **kwargs
        }

    async def send_message(
        self,
        channel: str,
        message: str,
        msg_type: str = "text"
    ) -> Dict[str, Any]:
        """
        发送消息（通过MCP）

        Args:
            channel: 渠道名称
            message: 消息内容
            msg_type: 消息类型

        Returns:
            发送结果
        """
        if channel not in self.channels:
            return {
                "success": False,
                "error": f"Channel '{channel}' not found"
            }

        config = self.channels[channel]
        channel_type = config["type"]
        webhook_url = config["webhook_url"]

        if not self._mcp_tools:
            return {
                "success": False,
                "error": "MCP tools not set, please call set_mcp_tools() first"
            }

        try:
            if channel_type == "feishu":
                return await self._send_via_mcp(
                    webhook_url=webhook_url,
                    payload={
                        "msg_type": msg_type,
                        "content": {"text": message}
                    }
                )
            elif channel_type == "dingtalk":
                return await self._send_via_mcp(
                    webhook_url=webhook_url,
                    payload={
                        "msgtype": msg_type,
                        "text": {"content": message}
                    }
                )
            else:
                return {
                    "success": False,
                    "error": f"Unsupported channel type: {channel_type}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _send_via_mcp(self, webhook_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """通过MCP发送HTTP请求"""
        # 使用http-mcp发送请求
        # http-mcp提供 http_request 工具
        if hasattr(self._mcp_tools, 'http_request'):
            result = await self._mcp_tools.http_request(
                method="POST",
                url=webhook_url,
                body=payload,
                headers={"Content-Type": "application/json"}
            )
            return {"success": True, "result": result}
        else:
            # 降级：返回结构化错误
            return {
                "success": False,
                "error": "http_request tool not available in MCP tools"
            }

    async def send_report(
        self,
        channel: str,
        report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        发送执行报告

        Args:
            channel: 渠道名称
            report: 执行报告内容

        Returns:
            发送结果
        """
        message = self._format_report(report)
        return await self.send_message(channel, message, "text")

    def _format_report(self, report: Dict[str, Any]) -> str:
        """格式化报告"""
        lines = [
            "📊 数栈智能体执行报告",
            "=" * 30,
            f"📋 计划: {report.get('plan_id', 'N/A')}",
            f"✅ 状态: {'成功' if report.get('success') else '失败'}",
            f"⏱️ 耗时: {report.get('duration', 0):.2f}秒",
            f"📝 步骤: {report.get('steps_executed', 0)} 成功, {report.get('steps_failed', 0)} 失败",
        ]

        if report.get('message'):
            lines.append(f"📌 详情: {report['message']}")

        return "\n".join(lines)

    def list_channels(self) -> List[str]:
        """列出所有配置的渠道"""
        return list(self.channels.keys())
