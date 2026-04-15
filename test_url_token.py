"""
测试将 token 放在 URL 参数中

关键发现：/api/project/list 说需要 token 在 URL 参数中验证！
"""

import asyncio
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_create_project_with_url_token():
    """测试创建项目时将 token 放在 URL 中"""
    print("="*60)
    print("  测试将 token 放在 URL 参数中")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    # 获取 cookie 和 token
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        pub_key_resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
        public_key = pub_key_resp.json().get("data")

        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        await client.post(
            f"{base_url}/uic/api/v2/account/login",
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )

        await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            data={"tenantId": "10451"}
        )

        cookie = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])
        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
        cookie += f"; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={dt_cookie_time}; dt_is_tenant_admin=true; dt_is_tenant_creator=true"

        # 获取 dt_token
        dt_token = None
        for k, v in client.cookies.items():
            if k == "dt_token":
                dt_token = v
                break

    if not dt_token:
        print("未找到 dt_token")
        return

    print(f"dt_token: {dt_token[:80]}...")

    # 测试 1: 只用 URL token，不带 cookie
    print("\n--- 测试 1: URL token + 无 cookie ---")
    url_with_token = f"{base_url}/api/rdos/common/project/createProject?token={urllib.parse.quote(dt_token)}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url_with_token,
            headers={"Content-Type": "text/plain;charset=UTF-8"},
            content=json.dumps({
                "projectName": "test_url_token_1",
                "projectAlias": "test_url_token_1",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )
        print(f"响应: {resp.status_code} - {resp.text[:300]}")

    # 测试 2: URL token + cookie
    print("\n--- 测试 2: URL token + cookie ---")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url_with_token,
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Cookie": cookie
            },
            content=json.dumps({
                "projectName": "test_url_token_2",
                "projectAlias": "test_url_token_2",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )
        print(f"响应: {resp.status_code} - {resp.text[:300]}")

    # 测试 3: URL token + 项目列表
    print("\n--- 测试 3: URL token + 项目列表 ---")
    url_list = f"{base_url}/api/project/list?token={urllib.parse.quote(dt_token)}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url_list,
            headers={"Content-Type": "text/plain;charset=UTF-8"}
        )
        print(f"响应: {resp.status_code} - {resp.text[:500]}")


async def test_project_list_with_auth():
    """
    测试不同的认证方式访问项目列表
    """
    print("\n" + "="*60)
    print("  测试项目列表 API 的认证方式")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        pub_key_resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
        public_key = pub_key_resp.json().get("data")

        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        await client.post(
            f"{base_url}/uic/api/v2/account/login",
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )

        await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            data={"tenantId": "10451"}
        )

        cookie = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])
        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
        cookie += f"; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={dt_cookie_time}; dt_is_tenant_admin=true; dt_is_tenant_creator=true"

        dt_token = None
        for k, v in client.cookies.items():
            if k == "dt_token":
                dt_token = v
                break

        # 测试不同的项目列表 API
        apis = [
            # Cookie 认证
            (f"{base_url}/api/rdos/common/project/list", "GET", {"Cookie": cookie}),
            (f"{base_url}/api/rdos/common/project/list", "POST", {"Cookie": cookie, "Content-Type": "text/plain;charset=UTF-8"}),
            # URL token 认证
            (f"{base_url}/api/rdos/common/project/list?token={dt_token}", "GET", {}),
            # Bearer token
            (f"{base_url}/api/rdos/common/project/list", "GET", {"Authorization": f"Bearer {dt_token}"}),
            # Basic Auth
            (f"{base_url}/api/rdos/common/project/list", "GET", {"Authorization": f"Basic {base64.b64encode(b'dtstack:dtstack').decode()}"}),
        ]

        for url, method, extra_headers in apis:
            print(f"\n{method} {url[:80]}...")
            headers = {"Accept": "application/json", **extra_headers}
            try:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                else:
                    resp = await client.post(url, headers=headers, content="{}")
                print(f"   {resp.status_code} - {resp.text[:200]}")
            except Exception as e:
                print(f"   Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_create_project_with_url_token())
    asyncio.run(test_project_list_with_auth())