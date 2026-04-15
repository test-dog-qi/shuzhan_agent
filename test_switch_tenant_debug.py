"""
测试租户切换 - 使用不同的 tenantId
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_switch_tenant_with_id(base_url: str, cookie: str, tenant_id: int, tenant_name: str):
    """测试使用指定 tenantId 切换租户"""
    print(f"\n{'='*60}")
    print(f"  测试切换到 tenantId={tenant_id} ({tenant_name})")
    print(f"{'='*60}")

    switch_url = f"{base_url}/uic/api/v2/account/user/switch-tenant"

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # 先获取初始 cookie
            resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
            print(f"获取公钥响应: {resp.status_code}")

            switch_resp = await client.post(
                switch_url,
                headers={
                    "Accept": "*/*",
                    "Cookie": cookie,
                    "Origin": base_url,
                    "Referer": f"{base_url}/publicService/",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
                },
                data={"tenantId": str(tenant_id)}
            )

            print(f"切换租户响应状态: {switch_resp.status_code}")

            # 提取所有 cookies
            cookie_parts = []
            for key, value in resp.cookies.items():
                cookie_parts.append(f"{key}={value}")

            for cookie_header in switch_resp.headers.get_list("set-cookie"):
                if cookie_header:
                    parts = cookie_header.split(";")
                    if parts:
                        name_value = parts[0].strip()
                        cookie_parts.append(name_value)

            full_cookie = "; ".join(cookie_parts)

            # 检查是否有我们需要的 cookie
            if "dt_tenant_id" in full_cookie:
                import re
                match = re.search(r'dt_tenant_id=([^;]+)', full_cookie)
                if match:
                    print(f"dt_tenant_id: {match.group(1)}")

            if "dt_tenant_name" in full_cookie:
                match = re.search(r'dt_tenant_name=([^;]+)', full_cookie)
                if match:
                    print(f"dt_tenant_name: {match.group(1)}")

            print(f"Cookie 长度: {len(full_cookie)}")

            return full_cookie

    except Exception as e:
        print(f"切换租户失败: {e}")
        return None


async def test_create_project(base_url: str, cookie: str, project_name: str):
    """测试创建项目"""
    print(f"\n{'='*60}")
    print(f"  测试创建项目: {project_name}")
    print(f"{'='*60}")

    create_url = f"{base_url}/api/rdos/common/project/createProject"

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # 设置 Cookie header
            headers = {
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json",
                "Cookie": cookie
            }

            response = await client.post(
                create_url,
                headers=headers,
                content=json.dumps({
                    "projectName": project_name,
                    "projectAlias": project_name,
                    "projectEngineList": [{"createModel": 0, "engineType": 1}],
                    "isAllowDownload": 1,
                    "scheduleStatus": 0,
                    "projectOwnerId": "1"
                })
            )

            print(f"响应状态: {response.status_code}")
            print(f"响应内容: {response.text[:1000]}")

            return response.text

    except Exception as e:
        print(f"创建项目失败: {e}")
        return None


def generate_dt_cookie_time():
    """生成 dt_cookie_time"""
    from datetime import datetime
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")


async def get_initial_cookies(base_url: str):
    """获取初始 cookies（不带任何认证）"""
    print(f"\n获取初始 cookies 从 {base_url}")

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")

            cookie_parts = []
            for key, value in resp.cookies.items():
                cookie_parts.append(f"{key}={value}")

            # 添加必要的 hardcoded cookies
            cookie_parts.extend([
                "dt_expire_cycle=0",
                "track_rdos=true",
                "dt_product_code=RDOS",
                f"dt_cookie_time={generate_dt_cookie_time()}"
            ])

            full_cookie = "; ".join(cookie_parts)
            print(f"初始 Cookie: {full_cookie[:200]}...")
            return full_cookie

    except Exception as e:
        print(f"获取初始 cookies 失败: {e}")
        return ""


async def main():
    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    print("="*60)
    print("  租户切换测试")
    print("="*60)

    # 1. 获取初始 cookies
    initial_cookie = await get_initial_cookies(base_url)

    # 2. 测试切换到 tenantId=1 (DT_demo)
    print("\n\n步骤1: 测试 tenantId=1 (DT_demo)")
    cookie_1 = await test_switch_tenant_with_id(base_url, initial_cookie, 1, "DT_demo")

    # 3. 测试创建项目
    if cookie_1:
        await test_create_project(base_url, cookie_1, "test_tenant_1_demo")

    # 4. 测试切换到 tenantId=10451 (ks_test)
    print("\n\n步骤2: 测试 tenantId=10451 (ks_test)")
    cookie_2 = await test_switch_tenant_with_id(base_url, initial_cookie, 10451, "ks_test")

    # 5. 测试创建项目
    if cookie_2:
        await test_create_project(base_url, cookie_2, "test_tenant_10451_ks")


if __name__ == "__main__":
    asyncio.run(main())