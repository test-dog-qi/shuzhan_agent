"""
测试特殊请求头

可能需要的特殊 header：
- X-Requested-With
- X-Forwarded-For
- X-DTStack-*
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_special_headers():
    """测试特殊请求头"""
    print("="*60)
    print("  测试特殊请求头")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 登录
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

        # 构建完整 cookie
        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
        cookie_parts = [f"{k}={v}" for k, v in client.cookies.items()]
        cookie_parts.extend([
            "dt_expire_cycle=0",
            "track_rdos=true",
            "dt_product_code=RDOS",
            f"dt_cookie_time={dt_cookie_time}",
            "dt_is_tenant_admin=true",
            "dt_is_tenant_creator=true"
        ])
        cookie_str = "; ".join(cookie_parts)

        # 打印使用的 cookie
        print(f"\n使用的 Cookie:")
        for part in cookie_str.split("; "):
            key = part.split("=")[0]
            if key in ["dt_token", "dt_tenant_id", "dt_tenant_name", "sysLoginType"]:
                print(f"  {key}: {part[:100]}...")

        # dt_token
        dt_token = client.cookies.get("dt_token", "")

        # 测试不同的请求头组合
        headers_combinations = [
            # 基础
            {
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json",
                "Cookie": cookie_str
            },
            # 添加 X-Requested-With
            {
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json",
                "Cookie": cookie_str,
                "X-Requested-With": "XMLHttpRequest"
            },
            # 添加完整的浏览器请求头
            {
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json",
                "Cookie": cookie_str,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Referer": f"{base_url}/",
                "Origin": base_url,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate"
            },
            # 添加 Dtstack 特有的 header
            {
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json",
                "Cookie": cookie_str,
                "X-DTStack-Token": dt_token,
                "X-DTStack-User": "1",
                "X-DTStack-Tenant": "10451"
            },
        ]

        payload = {
            "projectName": "test_headers",
            "projectAlias": "test_headers",
            "projectEngineList": [{"createModel": 0, "engineType": 1}],
            "isAllowDownload": 1,
            "scheduleStatus": 0,
            "projectOwnerId": "1"
        }

        for i, headers in enumerate(headers_combinations, 1):
            print(f"\n--- 测试 {i} ---")
            print(f"Headers: {[k for k in headers.keys() if k != 'Cookie' and k != 'X-DTStack-Token']}")

            resp = await client.post(
                f"{base_url}/api/rdos/common/project/createProject",
                headers=headers,
                content=json.dumps(payload)
            )
            result = resp.json()
            status = "✅" if result.get("success") else "❌"
            print(f"{status} {result.get('message', result.get('code'))}")


async def test_get_existing_projects():
    """
    尝试获取当前用户已有的项目列表

    也许问题是：用户需要在租户下有某些项目，或者需要被分配到某个角色
    """
    print("\n" + "="*60)
    print("  获取用户已有的项目")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 登录
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

        # 构建 cookie
        cookie_str = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])

        # 尝试获取用户可访问的项目
        project_apis = [
            f"{base_url}/api/rdos/common/project/getUserProjects",
            f"{base_url}/api/rdos/common/project/user/projects",
            f"{base_url}/api/rdos/common/project/listByUser",
        ]

        for api in project_apis:
            print(f"\nGET {api}")
            resp = await client.get(
                api,
                headers={
                    "Content-Type": "text/plain;charset=UTF-8",
                    "Cookie": cookie_str,
                    "Accept": "application/json"
                }
            )
            print(f"   {resp.status_code} - {resp.text[:300]}")


if __name__ == "__main__":
    asyncio.run(test_special_headers())
    asyncio.run(test_get_existing_projects())