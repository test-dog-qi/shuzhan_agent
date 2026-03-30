"""
数栈平台认证模块

保留认证业务逻辑，HTTP请求由MCP处理
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class AuthResult:
    """认证结果"""
    success: bool
    message: str
    token: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None
    user_info: Optional[Dict[str, Any]] = None


class DataStackAuthenticator:
    """
    数栈平台认证器

    负责构建认证请求，HTTP请求由MCP处理
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._mcp_tools: Optional[Any] = None

    def set_mcp_tools(self, mcp_tools: Any) -> None:
        """设置MCP工具集"""
        self._mcp_tools = mcp_tools

    def build_login_request(self, captcha_id: Optional[str] = None, captcha_code: Optional[str] = None) -> Dict[str, Any]:
        """
        构建登录请求参数

        Args:
            captcha_id: 验证码ID
            captcha_code: 验证码答案

        Returns:
            登录请求体
        """
        login_data = {
            "username": self.username,
            "password": self.password,
        }
        if captcha_id and captcha_code:
            login_data["captchaId"] = captcha_id
            login_data["captchaCode"] = captcha_code

        return login_data

    def build_captcha_request(self) -> Dict[str, Any]:
        """构建验证码请求参数"""
        return {
            "url": f"{self.base_url}/api/rdos/common/captcha/image",
            "method": "GET"
        }

    def parse_login_response(self, response: Dict[str, Any]) -> AuthResult:
        """
        解析登录响应

        Args:
            response: HTTP响应

        Returns:
            AuthResult
        """
        code = response.get("code", -1)
        if code == 0:
            data = response.get("data", {})
            self._token = data.get("token")
            return AuthResult(
                success=True,
                message="登录成功",
                token=self._token,
                user_info=data
            )
        else:
            return AuthResult(
                success=False,
                message=response.get("msg", "登录失败")
            )

    def get_auth_headers(self) -> Dict[str, str]:
        """获取认证请求头"""
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    @property
    def is_authenticated(self) -> bool:
        """是否已认证"""
        return self._token is not None


class CaptchaHandler:
    """
    验证码处理器

    使用MCP的图像识别能力解决验证码
    """

    def __init__(self, mcp_tools: Optional[Any] = None):
        self._mcp_tools = mcp_tools

    def set_mcp_tools(self, mcp_tools: Any) -> None:
        """设置MCP工具集"""
        self._mcp_tools = mcp_tools

    async def solve_captcha(self, image_data: bytes) -> str:
        """
        使用MCP图像识别解决验证码

        Args:
            image_data: 验证码图片字节数据

        Returns:
            验证码答案
        """
        if not self._mcp_tools:
            raise ValueError("MCP tools not set")

        # 使用everart-mcp进行图像识别
        # everart提供 image_to_text 工具
        if hasattr(self._mcp_tools, 'image_to_text'):
            result = await self._mcp_tools.image_to_text(
                image=image_data,
                prompt="请识别图片中的验证码文字或数字，只返回验证码内容"
            )
            return result.get("text", "").strip()
        else:
            raise ValueError("image_to_text tool not available in MCP tools")


class AuthManager:
    """
    认证管理器

    管理多个数栈环境的认证
    """

    def __init__(self):
        self._authenticators: Dict[str, DataStackAuthenticator] = {}

    def add_auth(self, env_name: str, authenticator: DataStackAuthenticator) -> None:
        """添加环境认证"""
        self._authenticators[env_name] = authenticator

    def get_auth(self, env_name: str) -> Optional[DataStackAuthenticator]:
        """获取环境认证"""
        return self._authenticators.get(env_name)

    def list_auths(self) -> List[str]:
        """列出所有已配置的环境"""
        return list(self._authenticators.keys())


# 向后兼容别名
DataStackAuth = DataStackAuthenticator
