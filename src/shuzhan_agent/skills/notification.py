"""通知技能 - 飞书/钉钉"""

import httpx
from typing import Any, Dict, Optional


class NotificationSkill:
    """
    通知技能

    支持多种通知渠道：
    - 飞书 Webhook
    - 钉钉 Webhook
    - 邮件（可选）
    """

    def __init__(self):
        self.channels: Dict[str, Dict[str, Any]] = {}

    def add_channel(self, name: str, channel_type: str, webhook_url: str, **kwargs):
        """
        添加通知渠道

        Args:
            name: 渠道名称
            channel_type: 渠道类型 (feishu/dingtalk/email)
            webhook_url: Webhook地址
            **kwargs: 其他配置
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
        发送消息

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

        try:
            if channel_type == "feishu":
                return await self._send_feishu(webhook_url, message, msg_type)
            elif channel_type == "dingtalk":
                return await self._send_dingtalk(webhook_url, message, msg_type)
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

    async def _send_feishu(
        self,
        webhook_url: str,
        message: str,
        msg_type: str
    ) -> Dict[str, Any]:
        """发送飞书消息"""
        payload = {
            "msg_type": msg_type,
            "content": {
                "text": message
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload)
            result = response.json()

            if result.get("code") == 0 or result.get("StatusCode") == 0:
                return {"success": True, "result": result}
            else:
                return {"success": False, "error": result.get("msg", "Unknown error")}

    async def _send_dingtalk(
        self,
        webhook_url: str,
        message: str,
        msg_type: str
    ) -> Dict[str, Any]:
        """发送钉钉消息"""
        payload = {
            "msgtype": msg_type,
            "text": {
                "content": message
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload)
            result = response.json()

            if result.get("errcode") == 0:
                return {"success": True, "result": result}
            else:
                return {"success": False, "error": result.get("errmsg", "Unknown error")}

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
        # 格式化报告为消息
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
