"""验证码处理模块"""

import asyncio
import httpx
from abc import ABC, abstractmethod
from typing import Optional


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


class OCRCaptchaSolver(CaptchaSolver):
    """
    基于OCR的验证码解决器

    适用于简单的数字/字母验证码
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def solve(self, image_data: bytes) -> str:
        """使用OCR识别验证码"""
        # 这里可以集成各种OCR服务
        # 1. MiniMax/其他AI API的图像识别
        # 2. 第三方OCR服务（如阿里云、腾讯云）
        # 3. 开源OCR（如Tesseract）

        # 示例：使用占位符，实际需要接入真实OCR
        # 推荐使用 MiniMax Vision API 或腾讯云 OCR

        # 伪代码示例：
        # from volcengine.visual.VisualClient import VisualClient
        # client = VisualClient(api_key, secret_key)
        # result = client.captcha_recognize(image_data)
        # return result.text

        raise NotImplementedError("需要配置真实的OCR服务")


class AIMCaptchaSolver(CaptchaSolver):
    """
    基于AI模型的验证码解决器

    使用视觉大模型识别验证码
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    async def solve(self, image_data: bytes) -> str:
        """使用视觉AI模型识别验证码"""
        # 使用MiniMax或其他视觉API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/captcha/recognize",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"image": image_data}
            )
            result = response.json()
            return result.get("text", "")


class CaptchaHandler:
    """
    验证码处理器

    负责处理登录流程中的验证码
    """

    def __init__(self, solver: Optional[CaptchaSolver] = None):
        self.solver = solver

    async def handle_login_captcha(self, session: httpx.AsyncClient, captcha_url: str) -> str:
        """
        获取并解决登录验证码

        Args:
            session: HTTP客户端会话
            captcha_url: 验证码获取URL

        Returns:
            验证码答案
        """
        # 1. 获取验证码图片
        response = await session.get(captcha_url)
        image_data = response.content

        # 2. 使用solver解决验证码
        if self.solver:
            return await self.solver.solve(image_data)

        raise ValueError("未配置验证码解决器")

    def set_solver(self, solver: CaptchaSolver) -> None:
        """设置验证码解决器"""
        self.solver = solver


# 推荐的可选验证码MCP Server
CAPTCHA_MCP_SERVERS = [
    {
        "name": "everart",
        "description": "图像识别MCP，支持OCR",
        "command": "npx -y @modelcontextprotocol/server-everart",
    },
    {
        "name": "azure-ai-vision",
        "description": "Azure计算机视觉",
        "command": "npx -y @azure/mcp-servers/cognitive-services/vision",
    },
]
