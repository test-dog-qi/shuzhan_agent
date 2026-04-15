"""
使用 Playwright 捕获浏览器创建项目的完整请求

目标：
1. 在浏览器中登录数栈
2. 点击创建项目
3. 捕获所有相关的网络请求和响应
4. 分析成功请求的 header 和 body
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


class RequestCapture:
    """捕获网络请求"""

    def __init__(self):
        self.requests: List[Dict[str, Any]] = []
        self.create_project_requests: List[Dict[str, Any]] = []

    async def setup(self, page):
        """设置请求拦截"""
        async def handle_request(request):
            self.requests.append({
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
                "post_data": request.post_data,
                "timing": request.timing
            })

            # 特别关注 createProject 请求
            if "createProject" in request.url:
                print(f"\n🔥 捕获到 createProject 请求:")
                print(f"   URL: {request.url}")
                print(f"   Method: {request.method}")
                print(f"   Headers: {dict(request.headers)}")
                if request.post_data:
                    print(f"   Body: {request.post_data}")
                self.create_project_requests.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "post_data": request.post_data
                })

        async def handle_response(response):
            # 关注 createProject 响应
            if "createProject" in response.url:
                try:
                    body = await response.text()
                    print(f"\n🔥 createProject 响应:")
                    print(f"   Status: {response.status}")
                    print(f"   Body: {body[:500]}")
                except:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)


async def manual_browser_test():
    """
    手动在浏览器中操作并捕获请求

    用户需要：
    1. 在打开的浏览器中登录
    2. 手动点击创建项目
    3. 观察捕获的请求
    """
    print("="*60)
    print("  Playwright 浏览器测试")
    print("="*60)
    print("\n这个测试会打开一个浏览器窗口。")
    print("请在浏览器中：")
    print("1. 登录数栈平台")
    print("2. 导航到项目管理页面")
    print("3. 点击创建项目按钮")
    print("4. 填写项目信息并提交")
    print("\n按 Ctrl+C 结束测试，将打印捕获的所有请求。\n")

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    capture = RequestCapture()

    async with BrowserAutomation(headless=False) as browser:
        await capture.setup(browser._page)

        # 导航到主页
        print(f"导航到: {base_url}")
        await browser.navigate(base_url)

        # 等待用户操作
        print("\n等待您在浏览器中操作...（按 Ctrl+C 停止）")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

        # 打印捕获的请求
        print("\n" + "="*60)
        print("  捕获到的 createProject 请求")
        print("="*60)

        if capture.create_project_requests:
            for req in capture.create_project_requests:
                print(f"\nURL: {req['url']}")
                print(f"Method: {req['method']}")
                print(f"Headers: {json.dumps(req['headers'], indent=2)}")
                print(f"Body: {req['post_data']}")
        else:
            print("没有捕获到 createProject 请求")

        # 打印所有相关的 API 请求
        print("\n" + "="*60)
        print("  所有相关的 API 请求")
        print("="*60)

        for req in capture.requests:
            url = req["url"]
            if any(keyword in url for keyword in ["/api/", "/uic/", "rdos", "project"]):
                print(f"\n{req['method']} {url}")
                if req.get("post_data"):
                    print(f"  Body: {req['post_data'][:200]}")


async def quick_capture_test():
    """
    快速捕获测试 - 登录后尝试某些操作并捕获请求
    """
    print("="*60)
    print("  快速捕获测试")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    capture = RequestCapture()

    async with BrowserAutomation(headless=False) as browser:
        await capture.setup(browser._page)

        # 登录
        print("\n1. 在浏览器中登录...")
        result = await browser.login_datastack(
            url=base_url,
            username=username,
            password=password
        )
        print(f"登录结果: {result.get('message')}")

        if result.get("success"):
            # 导航到项目管理页面
            print("\n2. 导航到项目管理页面...")
            await browser.navigate(f"{base_url}/#/project")
            await asyncio.sleep(3)

            # 截图看看当前页面
            await browser.screenshot("project_page.png")
            print("已截图: project_page.png")

        # 等待一段时间捕获请求
        print("\n等待捕获请求...")
        await asyncio.sleep(5)

        # 打印捕获的请求
        print("\n" + "="*60)
        print("  捕获到的 API 请求")
        print("="*60)

        for req in capture.requests:
            url = req["url"]
            if any(keyword in url for keyword in ["/api/", "/uic/", "rdos"]):
                print(f"\n{req['method']} {url}")
                if req.get("post_data"):
                    print(f"  Body: {str(req['post_data'])[:300]}")


async def main():
    print("\n选择测试模式:")
    print("1. 手动模式 - 打开浏览器，你手动操作，捕获请求")
    print("2. 快速模式 - 自动登录，导航到项目页面，捕获请求")

    choice = input("\n请选择 (1/2): ").strip() or "1"

    if choice == "1":
        await manual_browser_test()
    else:
        await quick_capture_test()


if __name__ == "__main__":
    asyncio.run(main())