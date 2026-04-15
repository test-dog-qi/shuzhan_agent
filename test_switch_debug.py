"""
测试 tenantId=10451 的 switch-tenant
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_switch_10451():
    """测试 tenantId=10451"""
    print("="*60)
    print("  测试 tenantId=10451")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

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

        # 提取登录 cookie
        login_cookie = ""
        for h in login_resp.headers.get_list("set-cookie"):
            if h.startswith("dt_token="):
                login_cookie = h.split(";")[0]
                break

        print(f"登录 cookie: {login_cookie[:80]}...")

        # 2. 切换到 tenantId=10451
        print(f"\n切换到 tenantId=10451...")
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

        # 检查 Set-Cookie 头
        set_cookie_headers = switch_resp.headers.get_list("set-cookie")
        print(f"\nSet-Cookie 头数量: {len(set_cookie_headers)}")

        # 统计 dt_token
        dt_token_count = sum(1 for h in set_cookie_headers if "dt_token=" in h)
        print(f"dt_token 数量: {dt_token_count}")

        for i, h in enumerate(set_cookie_headers):
            if "dt_token=" in h:
                print(f"\n  [{i}] dt_token:")
                print(f"      {h[:150]}...")

        # 3. 使用修改后的逻辑提取 cookie
        print(f"\n--- 使用修改后的逻辑提取 cookie ---")

        switch_cookie_parts = []
        seen_cookie_names = set()
        first_dt_token_found = False

        for cookie_header in set_cookie_headers:
            if cookie_header:
                parts = cookie_header.split(";")
                if parts and parts[0].strip():
                    name_value = parts[0].strip()
                    cookie_name = name_value.split("=")[0] if "=" in name_value else ""

                    if cookie_name == "dt_token":
                        if first_dt_token_found:
                            print(f"  跳过后续 dt_token")
                            continue
                        first_dt_token_found = True

                    if cookie_name not in seen_cookie_names:
                        switch_cookie_parts.append(name_value)
                        seen_cookie_names.add(cookie_name)
                        print(f"  添加: {cookie_name}")

        switch_cookie = "; ".join(switch_cookie_parts)
        print(f"\n最终 switch_cookie: {switch_cookie[:200]}...")

        # 4. 测试创建项目
        print(f"\n--- 测试创建项目 ---")

        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
        full_cookie = merge_cookies([login_cookie, switch_cookie + f"; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={dt_cookie_time}"])

        print(f"完整 cookie: {full_cookie[:200]}...")

        create_resp = await client.post(
            f"{base_url}/api/rdos/common/project/createProject",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json",
            },
            content=json.dumps({
                "projectName": "test_10451_v2",
                "projectAlias": "test_10451_v2",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )
        result = create_resp.json()
        print(f"创建结果: {result}")


def merge_cookies(cookie_strs: list) -> str:
    """合并 cookie 字符串"""
    cookie_dict = {}
    for cookie_str in cookie_strs:
        if not cookie_str:
            continue
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            key = part.split("=")[0]
            cookie_dict[key] = part
    return "; ".join(cookie_dict.values())


if __name__ == "__main__":
    asyncio.run(test_switch_10451())