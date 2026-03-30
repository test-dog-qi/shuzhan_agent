"""数栈平台认证模块"""

import asyncio
import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class AuthResult:
    """认证结果"""
    success: bool
    message: str
    cookies: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None
    user_info: Optional[Dict[str, Any]] = None


class DataStackAuth:
    """
    数栈平台认证

    支持账号密码登录和验证码处理
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        captcha_handler=None
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.captcha_handler = captcha_handler
        self._session: Optional[httpx.AsyncClient] = None
        self._is_logged_in = False

    async def login(self) -> AuthResult:
        """
        执行登录

        Returns:
            AuthResult: 登录结果
        """
        async with httpx.AsyncClient(
            base_url=self.base_url,
            follow_redirects=True,
            timeout=30.0
        ) as client:
            # 1. 获取登录页面（如果有验证码，先获取验证码）
            captcha_id, captcha_image = await self._get_captcha(client)
            captcha_code = None

            if captcha_id and self.captcha_handler:
                captcha_code = await self.captcha_handler.handle_login_captcha(
                    client,
                    f"{self.base_url}/api/rdos/common/captcha/image"
                )

            # 2. 执行登录
            login_data = {
                "username": self.username,
                "password": self.password,
            }
            if captcha_id:
                login_data["captchaId"] = captcha_id
                login_data["captchaCode"] = captcha_code

            try:
                response = await client.post(
                    "/api/rdos/common/user/login",
                    json=login_data
                )
                result = response.json()

                if response.status_code == 200 and result.get("code") == 0:
                    self._is_logged_in = True
                    # 提取cookies
                    cookies = {k: v for k, v in response.cookies.items()}
                    headers = {"Authorization": f"Bearer {result.get('data', {}).get('token')}"}

                    return AuthResult(
                        success=True,
                        message="登录成功",
                        cookies=cookies,
                        headers=headers,
                        user_info=result.get("data")
                    )
                else:
                    return AuthResult(
                        success=False,
                        message=result.get("msg", "登录失败")
                    )

            except Exception as e:
                return AuthResult(
                    success=False,
                    message=f"登录异常: {str(e)}"
                )

    async def _get_captcha(self, client: httpx.AsyncClient) -> tuple:
        """获取验证码"""
        try:
            response = await client.get("/api/rdos/common/captcha/image")
            if response.status_code == 200:
                result = response.json()
                captcha_id = result.get("data", {}).get("captchaId")
                image_data = response.content
                return captcha_id, image_data
        except Exception:
            pass
        return None, None

    async def get_session(self) -> httpx.AsyncClient:
        """获取已认证的会话"""
        if not self._is_logged_in:
            result = await self.login()
            if not result.success:
                raise ValueError(f"登录失败: {result.message}")

        headers = {}
        if hasattr(self, '_auth_headers'):
            headers = self._auth_headers

        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            follow_redirects=True,
            timeout=30.0
        )

    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self._is_logged_in


class AuthManager:
    """
    认证管理器

    管理多个数栈环境的认证
    """

    def __init__(self):
        self._auths: Dict[str, DataStackAuth] = {}

    def add_auth(self, env_name: str, auth: DataStackAuth) -> None:
        """添加环境认证"""
        self._auths[env_name] = auth

    def get_auth(self, env_name: str) -> Optional[DataStackAuth]:
        """获取环境认证"""
        return self._auths.get(env_name)

    async def login_all(self) -> Dict[str, AuthResult]:
        """登录所有环境"""
        results = {}
        for name, auth in self._auths.items():
            results[name] = await auth.login()
        return results
