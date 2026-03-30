"""
验证码解决器 - MCP封装

使用MCP的图像识别能力解决验证码
无需自己实现OCR逻辑
"""

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..agent.base import Tool


class CaptchaSolver(ABC):
    """验证码解决器基类"""

    @abstractmethod
    async def solve(self, image_data: bytes) -> str:
        """
        解决验证码

        Args:
            image_data: 验证码图片的字节数据

        Returns:
            验证码答案
        """
        pass


class MCPCaptchaSolver(CaptchaSolver):
    """
    基于MCP的验证码解决器

    使用everart-mcp等图像识别MCP
    """

    def __init__(self, mcp_tools: Optional["Tool"] = None):
        """
        Args:
            mcp_tools: MCP工具集（需包含image_to_text工具）
        """
        self._mcp_tools = mcp_tools

    def set_mcp_tools(self, mcp_tools: "Tool") -> None:
        """设置MCP工具"""
        self._mcp_tools = mcp_tools

    async def solve(self, image_data: bytes) -> str:
        """
        使用MCP图像识别解决验证码

        Args:
            image_data: 验证码图片字节数据

        Returns:
            验证码答案
        """
        if not self._mcp_tools:
            raise ValueError(
                "MCP tools not set. Please configure everart-mcp or similar image recognition MCP. "
                "Run: claude mcp add everart-mcp -- npx -y @modelcontextprotocol/server-everart"
            )

        # 使用MCP的图像识别能力
        # 尝试不同的MCP工具名称
        result = None

        if hasattr(self._mcp_tools, 'image_to_text'):
            result = await self._mcp_tools.image_to_text(
                image=image_data,
                prompt="请识别图片中的验证码字符，只返回验证码文字"
            )
        elif hasattr(self._mcp_tools, 'ocr'):
            result = await self._mcp_tools.ocr(image=image_data)
        elif hasattr(self._mcp_tools, 'recognize_captcha'):
            result = await self._mcp_tools.recognize_captcha(image=image_data)
        else:
            raise ValueError(
                f"MCP tools do not have image recognition capability. "
                f"Available tools: {dir(self._mcp_tools)}"
            )

        # 解析结果
        if isinstance(result, str):
            return result.strip()
        elif isinstance(result, dict):
            return result.get("text", result.get("content", "")).strip()
        else:
            return str(result).strip()


class CaptchaSolverFactory:
    """
    验证码解决器工厂

    根据配置的MCP创建对应的解决器
    """

    @staticmethod
    def create(mcp_tools: Optional["Tool"] = None) -> CaptchaSolver:
        """
        创建验证码解决器

        Args:
            mcp_tools: MCP工具集

        Returns:
            CaptchaSolver实例
        """
        if mcp_tools:
            return MCPCaptchaSolver(mcp_tools=mcp_tools)
        else:
            # 返回一个不解决问题的占位符
            return CaptchaSolver()


# 推荐的可选验证码MCP Server
CAPTCHA_MCP_SERVERS = [
    {
        "name": "everart",
        "description": "图像识别MCP，支持OCR和图像描述",
        "command": "npx -y @modelcontextprotocol/server-everart",
        "note": "需要配置API key"
    },
    {
        "name": "azure-vision",
        "description": "Azure计算机视觉",
        "command": "npx -y @azure/mcp-servers/cognitive-services/vision",
        "note": "需要Azure订阅"
    },
]
