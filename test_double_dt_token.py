"""
调试 dt_token 问题

问题分析：
- switch-tenant 返回多个 dt_token
- 第一个 dt_token 可以用于接口调用
- 第二个 dt_token 不能用

我们需要确认：
1. switch-tenant 是否真的返回了两个 dt_token
2. 是否正确处理了多个 dt_token 的情况
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_switch_tenant():
    """测试 switch-tenant 接口返回的 dt_token"""
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

        login_resp = await client.post(
            f"{base_url}/uic/api/v2/account/login",
            headers={
                "Accept": "application/json, text/plain, */*",
                "X-Custom-Header": "dtuic",
                "Referer": f"{base_url}/",
                "Origin": base_url,
            },
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )
        print(f"登录响应: {login_resp.json().get('message')}")

        login_cookie = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])

        # 2. 测试不同的 tenantId
        for tenant_id in ["1", "10451"]:
            print(f"\n{'='*60}")
            print(f"  切换到 tenantId={tenant_id}")
            print(f"{'='*60}")

            # 切换前清空相关 cookies
            if "dt_tenant_id" in client.cookies:
                del client.cookies["dt_tenant_id"]
            if "dt_tenant_name" in client.cookies:
                del client.cookies["dt_tenant_name"]
            if "dt_token" in client.cookies:
                del client.cookies["dt_token"]

            # 使用新的 cookie（不含旧的 tenant 相关）
            login_cookie = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])

            switch_resp = await client.post(
                f"{base_url}/uic/api/v2/account/user/switch-tenant",
                headers={
                    "Accept": "*/*",
                    "Cookie": login_cookie,
                    "Origin": base_url,
                    "Referer": f"{base_url}/publicService/",
                },
                data={"tenantId": tenant_id}
            )

            print(f"切换响应状态: {switch_resp.status_code}")
            print(f"切换响应头 set-cookie 数量: {len(switch_resp.headers.get_list('set-cookie'))}")

            # 分析 set-cookie 头
            set_cookie_headers = switch_resp.headers.get_list('set-cookie')
            dt_token_count = 0
            dt_tokens = []

            for i, header in enumerate(set_cookie_headers):
                if "dt_token=" in header:
                    dt_token_count += 1
                    # 提取 dt_token 的值
                    token_start = header.find("dt_token=") + len("dt_token=")
                    token_end = header.find(";", token_start)
                    if token_end == -1:
                        token_end = len(header)
                    dt_token = header[token_start:token_end]
                    dt_tokens.append(dt_token)
                    print(f"  第 {dt_token_count} 个 dt_token: {dt_token[:80]}...")

            print(f"\n共找到 {dt_token_count} 个 dt_token")

            # 解码所有 dt_token
            for i, token in enumerate(dt_tokens):
                parts = token.split(".")
                if len(parts) >= 2:
                    import base64
                    payload = parts[1]
                    payload += "=" * (4 - len(payload) % 4)
                    try:
                        decoded = base64.b64decode(payload)
                        payload_json = json.loads(decoded)
                        print(f"  dt_token[{i}] payload: {json.dumps(payload_json)}")
                    except:
                        print(f"  dt_token[{i}] 解码失败")

            # 3. 获取所有 cookies
            all_cookies = dict(client.cookies)
            current_dt_token = all_cookies.get("dt_token", "")

            if current_dt_token:
                parts = current_dt_token.split(".")
                if len(parts) >= 2:
                    import base64
                    payload = parts[1]
                    payload += "=" * (4 - len(payload) % 4)
                    try:
                        decoded = base64.b64decode(payload)
                        payload_json = json.loads(decoded)
                        print(f"\n当前 client.cookies 中的 dt_token payload: {json.dumps(payload_json)}")
                    except:
                        print(f"\n当前 dt_token 解码失败")

            # 4. 测试创建项目（使用 client.cookies 中的 dt_token）
            print(f"\n  测试创建项目...")
            create_resp = await client.post(
                f"{base_url}/api/rdos/common/project/createProject",
                headers={
                    "Content-Type": "text/plain;charset=UTF-8",
                    "Accept": "application/json"
                },
                content=json.dumps({
                    "projectName": f"test_{tenant_id}",
                    "projectAlias": f"test_{tenant_id}",
                    "projectEngineList": [{"createModel": 0, "engineType": 1}],
                    "isAllowDownload": 1,
                    "scheduleStatus": 0,
                    "projectOwnerId": "1"
                })
            )
            result = create_resp.json()
            print(f"  创建结果: {result.get('message', result.get('code'))}")


if __name__ == "__main__":
    asyncio.run(test_switch_tenant())