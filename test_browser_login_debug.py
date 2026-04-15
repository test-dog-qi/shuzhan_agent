"""
使用 Playwright 调试浏览器登录 - 捕获网络请求和 cookies

目标：观察浏览器登录数栈平台时的完整网络流程
1. 捕获所有 API 请求和响应
2. 对比浏览器 cookies 与 API 登录返回的 cookies
3. 找出导致 "无此用户" 错误的原因
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

from shuzhan_agent.mcp.playwright_integration import BrowserAutomation


class NetworkDebugger:
    """网络请求调试器"""

    def __init__(self):
        self.requests: List[Dict[str, Any]] = []
        self.responses: List[Dict[str, Any]] = []

    async def setup_route_interception(self, page):
        """设置路由拦截，捕获所有请求"""
        # 捕获请求
        async def handle_request(request):
            self.requests.append({
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
                "post_data": request.post_data
            })

        # 捕获响应
        async def handle_response(response):
            self.responses.append({
                "url": response.url,
                "status": response.status,
                "headers": dict(response.headers),
            })

        page.on("request", handle_request)
        page.on("response", handle_response)


async def debug_browser_login():
    """调试浏览器登录流程"""
    print("=" * 60)
    print("  Playwright 浏览器登录调试")
    print("=" * 60)

    # 获取凭证
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")
    login_url = "http://shuzhan62-online-test.k8s.dtstack.cn"

    debugger = NetworkDebugger()

    async with BrowserAutomation(headless=False) as browser:
        # 设置网络拦截
        await debugger.setup_route_interception(browser._page)

        print(f"\n1. 导航到登录页: {login_url}")
        await browser.navigate(login_url)
        await asyncio.sleep(2)

        print("\n2. 执行 UI 登录...")
        result = await browser.login_datastack(
            url=login_url,
            username=username,
            password=password
        )

        print(f"\n3. 登录结果: {result.get('message', 'unknown')}")
        print(f"   是否成功: {result.get('success')}")
        print(f"   当前URL: {result.get('url')}")

        # 等待一段时间以捕获所有网络请求
        await asyncio.sleep(3)

        # 打印捕获到的相关请求
        print("\n" + "=" * 60)
        print("  捕获到的 API 请求")
        print("=" * 60)

        relevant_domains = ["shuzhan62", "dtstack.cn", "/uic/", "/rdos/"]

        for req in debugger.requests:
            url = req["url"]
            if any(domain in url for domain in relevant_domains):
                print(f"\n请求: {req['method']} {url}")
                if req.get("post_data"):
                    print(f"  POST数据: {req['post_data'][:200] if len(str(req['post_data'])) > 200 else req['post_data']}")

        print("\n" + "=" * 60)
        print("  登录后的 Cookies")
        print("=" * 60)

        cookies = await browser.get_cookies()
        for name, value in cookies.items():
            if any(key in name.lower() for key in ["dt_", "sys", "track", "user", "tenant", "token"]):
                display_value = value[:100] + "..." if len(value) > 100 else value
                print(f"  {name}: {display_value}")

        # 特别关注 dt_token
        dt_token = cookies.get("dt_token", "")
        if dt_token:
            print(f"\n  dt_token 长度: {len(dt_token)}")
            # 尝试解码 JWT
            try:
                parts = dt_token.split(".")
                if len(parts) >= 2:
                    import base64
                    payload = parts[1]
                    # 添加 padding
                    payload += "=" * (4 - len(payload) % 4)
                    decoded = base64.b64decode(payload)
                    print(f"  dt_token payload: {json.loads(decoded)}")
            except Exception as e:
                print(f"  dt_token 解码失败: {e}")

    return cookies


async def test_api_calls_with_browser_cookies():
    """使用浏览器 cookies 测试 API 调用"""
    print("\n" + "=" * 60)
    print("  使用浏览器 Cookies 测试 API")
    print("=" * 60)

    # 先通过浏览器获取 cookies
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    async with BrowserAutomation(headless=False) as browser:
        print("\n1. 通过浏览器登录...")
        result = await browser.login_datastack(
            url="http://shuzhan62-online-test.k8s.dtstack.cn",
            username=username,
            password=password
        )

        if not result.get("success"):
            print(f"浏览器登录失败: {result}")
            return

        print("浏览器登录成功")

        # 获取 cookies
        cookies = await browser.get_cookies()

        # 构建 cookie 字符串
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        print(f"\n浏览器 cookie 字符串长度: {len(cookie_str)}")

        # 尝试创建项目
        print("\n2. 使用浏览器 cookies 调用创建项目 API...")

        import httpx

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "http://shuzhan62-online-test.k8s.dtstack.cn/api/rdos/common/project/createProject",
                    headers={
                        "Content-Type": "text/plain;charset=UTF-8",
                        "Accept": "application/json"
                    },
                    cookies=cookies,
                    content=json.dumps({
                        "projectName": "test_browser_0407_1",
                        "projectAlias": "test_browser_0407_1",
                        "projectEngineList": [{"createModel": 0, "engineType": 1}],
                        "isAllowDownload": 1,
                        "scheduleStatus": 0,
                        "projectOwnerId": "1"
                    })
                )
                print(f"响应状态: {response.status_code}")
                print(f"响应内容: {response.text[:500]}")
        except Exception as e:
            print(f"API 调用失败: {e}")


async def main():
    """主函数"""
    print("\n请选择调试模式:")
    print("1. 仅捕获浏览器登录的网络请求")
    print("2. 捕获登录并使用 cookies 测试 API")
    print("3. 完整调试（捕获网络 + 测试 API）")

    choice = input("\n请输入选择 (1/2/3): ").strip() or "3"

    if choice == "1":
        await debug_browser_login()
    elif choice == "2":
        await test_api_calls_with_browser_cookies()
    else:
        await debug_browser_login()
        await test_api_calls_with_browser_cookies()


if __name__ == "__main__":
    asyncio.run(main())