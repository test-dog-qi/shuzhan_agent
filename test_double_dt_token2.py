"""
调试 dt_token 问题 - 版本2
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
    print("  测试 switch-tenant 返回的 dt_token")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 1. 获取公钥并登录
        pub_key_resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
        public_key = pub_key_resp.json().get("data")

        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        await client.post(
            f"{base_url}/uic/api/v2/account/login",
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )

        print("登录后的 cookies:")
        for k, v in client.cookies.items():
            if k == "dt_token":
                print(f"  {k}: {v[:80]}... (payload: {decode_payload(v)})")
            else:
                print(f"  {k}: {v}")

        # 2. 测试 tenantId=10451
        print(f"\n{'='*60}")
        print(f"  切换到 tenantId=10451")
        print(f"{'='*60}")

        # 先清空 cookies 中的 tenant 相关字段
        for key in list(client.cookies.keys()):
            if "tenant" in key.lower() or key == "dt_token":
                del client.cookies[key]

        switch_resp = await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            headers={
                "Accept": "*/*",
                "Origin": base_url,
                "Referer": f"{base_url}/publicService/",
            },
            data={"tenantId": "10451"}
        )

        print(f"切换响应状态: {switch_resp.status_code}")

        # httpx 会自动处理 Set-Cookie，所以 cookies 应该已经更新
        print("\n切换后的 cookies:")
        for k, v in client.cookies.items():
            if k == "dt_token":
                print(f"  {k}: {v[:80]}... (payload: {decode_payload(v)})")
            elif "tenant" in k.lower():
                print(f"  {k}: {v}")

        # 3. 测试创建项目
        print(f"\n  测试创建项目...")
        cookie_str = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])
        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
        cookie_str += f"; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={dt_cookie_time}; dt_is_tenant_admin=true; dt_is_tenant_creator=true"

        create_resp = await client.post(
            f"{base_url}/api/rdos/common/project/createProject",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json",
            },
            content=json.dumps({
                "projectName": "test_10451",
                "projectAlias": "test_10451",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )
        result = create_resp.json()
        print(f"  创建结果: {result}")


if __name__ == "__main__":
    asyncio.run(test_switch_tenant())