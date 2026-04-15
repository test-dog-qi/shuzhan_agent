"""
深入分析：为什么浏览器能成功但 Postman 不能

用户提供的成功 curl：
```bash
curl 'http://shuzhan62-online-test.k8s.dtstack.cn/api/rdos/common/project/createProject' \
  -H 'Content-Type: text/plain;charset=UTF-8' \
  -b 'dt_expire_cycle=0; sysLoginType=...; dt_user_id=1; dt_username=...; dt_tenant_id=10451; dt_tenant_name=ks_test; dt_token=...eyJ0ZW5hbnRfaWQiOiIxMDQ1MSI...; dt_is_tenant_admin=true; dt_is_tenant_creator=true; dt_product_code=RDOS; track_rdos=true'
```

关键观察：
1. Content-Type: text/plain;charset=UTF-8 (不是 application/json)
2. dt_tenant_id=10451 (不是1)
3. dt_tenant_name=ks_test (不是DT_demo)
4. dt_token 包含 tenant_id: 10451
5. 有 dt_is_tenant_admin=true, dt_is_tenant_creator=true

测试目标：使用完全相同的请求头和 Cookie 格式来测试
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


def decode_jwt_payload(token: str) -> dict:
    """解码 JWT payload"""
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            return json.loads(decoded)
    except:
        return {}


def generate_dt_cookie_time():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")


async def get_browser_style_cookies():
    """
    获取浏览器风格的完整 cookies
    包括：sysLoginType, dt_tenant_id, dt_is_tenant_admin, dt_is_tenant_creator 等
    """
    print("="*60)
    print("  获取浏览器风格的完整 cookies")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 1. 先访问主页
        await client.get(base_url)

        # 2. 获取公钥
        pub_key_resp = await client.get(
            f"{base_url}/uic/api/v2/account/login/get-publi-key",
            headers={
                "Accept": "application/json, text/plain, */*",
                "X-Custom-Header": "dtuic",
                "Referer": f"{base_url}/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            }
        )
        pub_key_data = pub_key_resp.json()
        public_key = pub_key_data.get("data")

        # 3. 登录
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
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            },
            data={
                "username": username,
                "password": encrypted_password,
                "verify_code": "1",
                "key": "1"
            }
        )

        # 4. 切换租户 - 尝试 10451 (ks_test)
        switch_resp = await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            headers={
                "Accept": "*/*",
                "Cookie": "; ".join([f"{k}={v}" for k, v in client.cookies.items()]),
                "Origin": base_url,
                "Referer": f"{base_url}/publicService/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            },
            data={"tenantId": "10451"}  # 尝试 ks_test 租户
        )

        # 5. 构建完整的浏览器风格 cookie
        cookie_parts = []

        # 添加 client.cookies 中的所有内容
        for k, v in client.cookies.items():
            cookie_parts.append(f"{k}={v}")

        # 添加可能缺失的 cookie
        existing_keys = [p.split("=")[0] for p in cookie_parts]

        if "dt_expire_cycle" not in existing_keys:
            cookie_parts.append("dt_expire_cycle=0")
        if "track_rdos" not in existing_keys:
            cookie_parts.append("track_rdos=true")
        if "dt_product_code" not in existing_keys:
            cookie_parts.append("dt_product_code=RDOS")
        if "dt_cookie_time" not in existing_keys:
            cookie_parts.append(f"dt_cookie_time={generate_dt_cookie_time()}")
        if "dt_is_tenant_admin" not in existing_keys:
            cookie_parts.append("dt_is_tenant_admin=true")
        if "dt_is_tenant_creator" not in existing_keys:
            cookie_parts.append("dt_is_tenant_creator=true")

        full_cookie = "; ".join(cookie_parts)

        print(f"\n完整 Cookie ({len(full_cookie)} 字符):")
        for part in full_cookie.split(";"):
            part = part.strip()
            if part.startswith("dt_token="):
                print(f"  dt_token: {part[:80]}...")
                payload = decode_jwt_payload(part.split("=", 1)[1])
                print(f"  dt_token payload: {json.dumps(payload)}")

        # 检查关键 cookie
        for key in ["dt_tenant_id", "dt_tenant_name", "dt_is_tenant_admin", "dt_is_tenant_creator"]:
            for part in full_cookie.split(";"):
                if part.strip().startswith(f"{key}="):
                    print(f"  {key}: {part.strip().split('=', 1)[1]}")

        return full_cookie


async def test_create_project_exact_headers(cookie: str):
    """
    使用完全匹配的请求头测试创建项目
    完全模拟浏览器复制的 curl 请求
    """
    print("\n" + "="*60)
    print("  使用浏览器风格请求测试创建项目")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 完全模拟浏览器复制的 curl 请求
        response = await client.post(
            f"{base_url}/api/rdos/common/project/createProject",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",  # 关键：不是 application/json
                "Accept": "application/json",
                "Cookie": cookie
            },
            content=json.dumps({
                "projectName": "test_exact_match_0407",
                "projectAlias": "test_exact_match_0407",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )

        print(f"\n响应状态: {response.status_code}")
        print(f"响应内容: {response.text}")


async def test_with_session_context():
    """
    测试：是否需要先建立 session context 才能成功调用

    可能的问题：
    1. 某些 Cookie 需要在同一个 session 中设置
    2. 服务器验证 Cookie 时检查了 session 状态
    3. HTTP/2 multiplexing 问题
    """
    print("\n" + "="*60)
    print("  测试 session context 影响")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    # 使用同一个 client 保持 session
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 1. 先访问一些页面建立 context
        print("1. 建立 session context...")
        await client.get(f"{base_url}/")
        await asyncio.sleep(0.5)

        # 2. 登录
        print("2. 登录...")
        pub_key_resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
        public_key = pub_key_resp.json().get("data")

        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        login_resp = await client.post(
            f"{base_url}/uic/api/v2/account/login",
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )
        print(f"   登录响应: {login_resp.json()}")

        # 3. 切换租户
        print("3. 切换租户...")
        switch_resp = await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            data={"tenantId": "1"}
        )
        print(f"   切换响应状态: {switch_resp.status_code}")

        # 4. 在同一 session 中调用创建项目
        print("4. 在同一 session 中调用创建项目...")

        # 关键：使用 session 的 cookie
        session_cookie = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])

        # 添加 hardcoded
        session_cookie += "; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time=" + generate_dt_cookie_time()

        print(f"   Session Cookie: {session_cookie[:200]}...")

        create_resp = await client.post(
            f"{base_url}/api/rdos/common/project/createProject",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json"
            },
            content=json.dumps({
                "projectName": "test_session_context_0407",
                "projectAlias": "test_session_context_0407",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )
        print(f"   响应: {create_resp.status_code}")
        print(f"   内容: {create_resp.text}")


async def main():
    # 1. 获取浏览器风格的 cookies
    cookie = await get_browser_style_cookies()

    # 2. 使用完全匹配的请求头测试
    await test_create_project_exact_headers(cookie)

    # 3. 测试 session context
    await test_with_session_context()


if __name__ == "__main__":
    asyncio.run(main())