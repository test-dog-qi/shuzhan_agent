"""
调试 dt_token 问题 - 版本3
不使用 follow_redirects
"""

import asyncio
import json
import os
import sys
import base64

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


def decode_payload(token: str) -> dict:
    """解码 JWT payload"""
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            payload += "=" * (4 - len(payload) % 4)
            return json.loads(base64.b64decode(payload))
    except:
        return {}


async def test_switch_tenant():
    """测试 switch-tenant 接口"""
    print("="*60)
    print("  测试 switch-tenant 返回的 dt_token（禁用自动重定向）")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    # 不使用自动重定向
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        # 1. 获取公钥并登录
        pub_key_resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
        public_key = pub_key_resp.json().get("data")

        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        login_resp = await client.post(
            f"{base_url}/uic/api/v2/account/login",
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )

        print(f"登录响应状态: {login_resp.status_code}")
        print(f"登录响应 Set-Cookie 头:")
        for header in login_resp.headers.get_list("set-cookie"):
            if "dt_token" in header:
                print(f"  {header[:150]}...")

        login_cookie = login_resp.headers.get_list("set-cookie")[0] if login_resp.headers.get_list("set-cookie") else ""
        for h in login_resp.headers.get_list("set-cookie"):
            if h.startswith("dt_token="):
                login_cookie = h.split(";")[0]
                break

        print(f"\n从 Set-Cookie 提取的 dt_token: {login_cookie[:80] if login_cookie else 'None'}...")
        if login_cookie:
            print(f"  payload: {decode_payload(login_cookie.split('=')[1])}")

        # 2. 测试 tenantId=10451
        print(f"\n{'='*60}")
        print(f"  切换到 tenantId=10451")
        print(f"{'='*60}")

        switch_resp = await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            headers={
                "Accept": "*/*",
                "Cookie": login_cookie,
                "Origin": base_url,
                "Referer": f"{base_url}/publicService/",
            },
            data={"tenantId": "10451"}
        )

        print(f"切换响应状态: {switch_resp.status_code}")
        print(f"切换响应头:")
        for header in switch_resp.headers.get_list("set-cookie"):
            print(f"  {header[:200]}...")

        # 统计 dt_token 数量
        dt_token_count = sum(1 for h in switch_resp.headers.get_list("set-cookie") if "dt_token=" in h)
        print(f"\n共 {dt_token_count} 个 Set-Cookie 包含 dt_token")

        # 提取所有 dt_token
        dt_tokens = []
        for h in switch_resp.headers.get_list("set-cookie"):
            if "dt_token=" in h:
                # 提取 name=value; 前的部分
                token = h.split(";")[0].replace("dt_token=", "")
                dt_tokens.append(token)

        print(f"\n提取的 dt_token:")
        for i, token in enumerate(dt_tokens):
            print(f"  [{i}]: {token[:80]}... (payload: {decode_payload(token)})")

        # 3. 用第一个 dt_token 测试创建项目
        if dt_tokens:
            first_token = dt_tokens[0]
            print(f"\n{'='*60}")
            print(f"  使用第一个 dt_token 测试创建项目")
            print(f"{'='*60}")

            cookie = f"dt_token={first_token}; dt_tenant_id=10451; dt_tenant_name=ks_test; dt_is_tenant_admin=true; dt_is_tenant_creator=true; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time=2026-04-08+10%3A12%3A00"

            print(f"Cookie: {cookie[:200]}...")

            create_resp = await client.post(
                f"{base_url}/api/rdos/common/project/createProject",
                headers={
                    "Content-Type": "text/plain;charset=UTF-8",
                    "Accept": "application/json",
                    "Cookie": cookie
                },
                content=json.dumps({
                    "projectName": "test_first_token",
                    "projectAlias": "test_first_token",
                    "projectEngineList": [{"createModel": 0, "engineType": 1}],
                    "isAllowDownload": 1,
                    "scheduleStatus": 0,
                    "projectOwnerId": "1"
                })
            )
            result = create_resp.json()
            print(f"创建结果: {result}")


if __name__ == "__main__":
    asyncio.run(test_switch_tenant())