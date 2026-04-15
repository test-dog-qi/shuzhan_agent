"""
测试不同的 JSON payload 参数组合

用户提供的成功 curl：
- projectOwnerId="1"
- 但可能需要其他参数
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_different_payloads():
    """测试不同的 payload 参数"""
    print("="*60)
    print("  测试不同的 JSON payload")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    # 获取 cookie
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

    # 测试不同的 payload
    payloads = [
        # 原始 payload
        {
            "projectName": "test_payload1",
            "projectAlias": "test_payload1",
            "projectEngineList": [{"createModel": 0, "engineType": 1}],
            "isAllowDownload": 1,
            "scheduleStatus": 0,
            "projectOwnerId": "1"
        },
        # 只传必填字段
        {
            "projectName": "test_payload2",
            "projectAlias": "test_payload2",
            "projectEngineList": [{"createModel": 0, "engineType": 1}],
        },
        # 尝试不同的 engineType
        {
            "projectName": "test_payload3",
            "projectAlias": "test_payload3",
            "projectEngineList": [{"createModel": 0, "engineType": 2}],
        },
        # 尝试带 spaceId
        {
            "projectName": "test_payload4",
            "projectAlias": "test_payload4",
            "projectEngineList": [{"createModel": 0, "engineType": 1}],
            "spaceId": 1,
        },
        # 尝试 projectOwnerId = "0"
        {
            "projectName": "test_payload5",
            "projectAlias": "test_payload5",
            "projectEngineList": [{"createModel": 0, "engineType": 1}],
            "projectOwnerId": "0"
        },
    ]

    for i, payload in enumerate(payloads, 1):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url}/api/rdos/common/project/createProject",
                headers={
                    "Content-Type": "text/plain;charset=UTF-8",
                    "Accept": "application/json",
                    "Cookie": cookie
                },
                content=json.dumps(payload)
            )

            result = resp.json()
            status = "✅" if result.get("success") else "❌"
            print(f"\n{status} Payload {i}: {result.get('message', result.get('code'))}")
            print(f"   Payload: {json.dumps(payload)}")


async def test_user_info_api():
    """
    测试获取用户信息 API
    看看是否可以获取当前用户可用的 space/project 信息
    """
    print("\n" + "="*60)
    print("  测试用户信息 API")
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

        # 尝试获取用户信息
        print("\n1. 尝试获取用户信息...")
        user_resp = await client.get(
            f"{base_url}/uic/api/v2/account/user/info",
            headers={"Cookie": cookie}
        )
        print(f"   /uic/api/v2/account/user/info: {user_resp.status_code}")
        print(f"   {user_resp.text[:300]}")

        # 尝试获取租户下的项目列表
        print("\n2. 尝试获取项目列表...")
        projects_resp = await client.get(
            f"{base_url}/api/rdos/common/project/list",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Cookie": cookie
            }
        )
        print(f"   /api/rdos/common/project/list: {projects_resp.status_code}")
        print(f"   {projects_resp.text[:500]}")

        # 尝试不同的 list API
        print("\n3. 尝试其他 list API...")
        for path in [
            "/api/rdos/project/list",
            "/api/project/list",
            "/rdos/api/project/list",
        ]:
            resp = await client.get(
                f"{base_url}{path}",
                headers={"Cookie": cookie}
            )
            print(f"   {path}: {resp.status_code} - {resp.text[:100]}")


if __name__ == "__main__":
    asyncio.run(test_different_payloads())
    asyncio.run(test_user_info_api())