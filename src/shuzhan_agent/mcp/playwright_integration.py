"""
Playwright集成 - 直接在代码中使用Playwright

不依赖外部MCP Server，直接使用Playwright Python库
"""

import asyncio
from typing import Any, Dict, Optional, List
from dataclasses import dataclass
import re


@dataclass
class Cookie:
    """Cookie结构"""
    name: str
    value: str
    domain: str = ""
    path: str = "/"


class BrowserAutomation:
    """
    浏览器自动化 - 直接集成Playwright

    功能：
    1. 自动化登录（绕过验证码）
    2. 获取cookies
    3. 页面操作
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None  # 保持playwright引用防止被GC
        self._browser = None
        self._context = None
        self._page = None
        self._cookies: Dict[str, str] = {}

    async def initialize(self):
        """初始化浏览器 - 使用系统Chrome"""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        # 优先使用系统Chrome，避免下载问题
        try:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                channel="chrome"  # 使用系统Chrome
            )
        except Exception:
            # 如果系统Chrome不可用，使用默认chromium
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()

    async def navigate(self, url: str) -> Dict[str, Any]:
        """导航到URL"""
        if not self._page:
            await self.initialize()

        response = await self._page.goto(url, wait_until="networkidle")
        return {
            "url": url,
            "status": response.status if response else None,
            "title": await self._page.title() if self._page else None
        }

    async def click(self, selector: str) -> Dict[str, Any]:
        """点击元素"""
        if not self._page:
            return {"error": "Page not initialized"}

        try:
            await self._page.click(selector)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"error": str(e)}

    async def fill(self, selector: str, value: str) -> Dict[str, Any]:
        """填写表单"""
        if not self._page:
            return {"error": "Page not initialized"}

        try:
            await self._page.fill(selector, value)
            return {"success": True, "selector": selector, "value": value}
        except Exception as e:
            return {"error": str(e)}

    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> Dict[str, Any]:
        """等待元素出现"""
        if not self._page:
            return {"error": "Page not initialized"}

        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"error": str(e)}

    async def screenshot(self, path: str = "screenshot.png") -> Dict[str, Any]:
        """截图"""
        if not self._page:
            return {"error": "Page not initialized"}

        await self._page.screenshot(path=path)
        return {"success": True, "path": path}

    async def get_cookies(self) -> Dict[str, str]:
        """获取当前会话的cookies"""
        if not self._context:
            return {}

        cookies = await self._context.cookies()
        self._cookies = {c["name"]: c["value"] for c in cookies}
        return self._cookies

    async def login_datastack(
        self,
        url: str,
        username: str,
        password: str,
        selectors: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        自动化登录数栈平台

        Args:
            url: 登录页面URL
            username: 用户名
            password: 密码
            selectors: 元素选择器，如果为None使用默认选择器

        Returns:
            登录结果和cookies
        """
        if not self._page:
            await self.initialize()

        # 默认选择器
        if selectors is None:
            selectors = {
                "username_input": 'input[name="username"], input[type="text"]',
                "password_input": 'input[name="password"], input[type="password"]',
                "submit_button": 'button[type="submit"], input[type="submit"], .login-btn',
                "captcha_input": 'input[name="captcha"], input[name="verifyCode"]',
            }

        try:
            # 1. 导航到登录页
            await self.navigate(url)

            # 2. 填写用户名
            username_selector = selectors.get("username_input")
            if username_selector:
                try:
                    await self._page.fill(username_selector, username)
                    await asyncio.sleep(0.5)
                except:
                    # 尝试其他方式
                    await self._page.locator("input").first.fill(username)
                    await asyncio.sleep(0.5)

            # 3. 填写密码
            password_selector = selectors.get("password_input")
            if password_selector:
                try:
                    await self._page.fill(password_selector, password)
                except:
                    await self._page.locator("input[type='password']").first.fill(password)
                    await asyncio.sleep(0.5)

            # 4. 检查是否有验证码
            captcha_selector = selectors.get("captcha_input")
            if captcha_selector:
                try:
                    # 如果有验证码，等待用户输入或自动识别
                    captcha_box = self._page.locator(captcha_selector)
                    if await captcha_box.is_visible():
                        # 截取验证码图片
                        captcha_img = self._page.locator("img.captcha, .captcha-img, img[alt='captcha']")
                        if await captcha_img.count() > 0:
                            await captcha_img.first.screenshot(path="captcha.png")
                            # TODO: 使用视觉API识别验证码
                            return {
                                "success": False,
                                "need_captcha": True,
                                "message": "需要验证码识别"
                            }
                except:
                    pass

            # 5. 点击登录按钮
            submit_selector = selectors.get("submit_button")
            if submit_selector:
                await self._page.click(submit_selector)
            else:
                await self._page.locator("button").last.click()

            # 6. 等待登录完成
            await asyncio.sleep(3)

            # 7. 获取cookies
            cookies = await self.get_cookies()

            # 8. 检查登录是否成功
            current_url = self._page.url
            if "login" not in current_url.lower():
                return {
                    "success": True,
                    "cookies": cookies,
                    "url": current_url,
                    "message": "登录成功"
                }
            else:
                return {
                    "success": False,
                    "cookies": cookies,
                    "url": current_url,
                    "message": "登录可能失败，仍在登录页"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def close(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()

    def get_auth_cookies(self) -> Dict[str, str]:
        """获取认证cookies"""
        return self._cookies.copy()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class VisionCaptchaSolver:
    """
    视觉验证码识别器

    使用MiniMax视觉API识别验证码
    """

    def __init__(self, api_key: str, base_url: str = "https://api.minimaxi.com"):
        self.api_key = api_key
        self.base_url = base_url

    async def solve_captcha(self, image_path: str) -> str:
        """
        识别验证码图片

        Args:
            image_path: 验证码图片路径

        Returns:
            验证码答案
        """
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key, base_url=self.base_url)

        with open(image_path, "rb") as f:
            image_data = f.read()

        # 使用视觉模型识别
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data.hex()
                        }
                    },
                    {
                        "type": "text",
                        "text": "请识别这张图片中的验证码文字或数字，只返回验证码内容，不要其他文字。"
                    }
                ]
            }]
        )

        return response.content[0].text.strip()
