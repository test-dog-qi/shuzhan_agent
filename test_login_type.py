"""
测试 sysLoginType cookie 的影响

用户提供的成功 curl 中有：
- sysLoginType (我们的 API 登录没有这个)

这可能是关键差异！
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_with_sysLoginType():
    """测试添加 sysLoginType cookie"""
    print("="*60)
    print("  测试 sysLoginType cookie 的影响")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    # 先正常登录获取 cookies
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 获取公钥
        pub_key_resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
        public_key = pub_key_resp.json().get("data")

        # 登录
        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        login_resp = await client.post(
            f"{base_url}/uic/api/v2/account/login",
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )
        print(f"登录: {login_resp.json()}")

        # 切换租户到 10451
        switch_resp = await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            data={"tenantId": "10451"}
        )
        print(f"切换租户: {switch_resp.status_code}")

        # 构建 cookie 字符串
        cookie_parts = [f"{k}={v}" for k, v in client.cookies.items()]

        # 尝试不同的 sysLoginType 值
        sys_login_type_values = [
            "LDAP", "DATABASE", "OAUTH2", "CAS", "SSO", "FORM",
            "1", "2", "3", "true", "false", ""
        ]

        for sys_login_type in sys_login_type_values:
            # 添加所有可能的 cookie
            from datetime import datetime
            dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")

            test_cookies = "; ".join(cookie_parts)
            if sys_login_type:
                test_cookies += f"; sysLoginType={sys_login_type}"
            test_cookies += f"; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={dt_cookie_time}; dt_is_tenant_admin=true; dt_is_tenant_creator=true"

            # 测试创建项目
            create_resp = await client.post(
                f"{base_url}/api/rdos/common/project/createProject",
                headers={
                    "Content-Type": "text/plain;charset=UTF-8",
                    "Accept": "application/json"
                },
                content=json.dumps({
                    "projectName": f"test_sysLoginType_{sys_login_type or 'none'}",
                    "projectAlias": f"test_sysLoginType_{sys_login_type or 'none'}",
                    "projectEngineList": [{"createModel": 0, "engineType": 1}],
                    "isAllowDownload": 1,
                    "scheduleStatus": 0,
                    "projectOwnerId": "1"
                })
            )

            result = create_resp.json()
            status = "✅" if result.get("success") else "❌"
            print(f"{status} sysLoginType={sys_login_type or '(none)'}: {result.get('message', result.get('code'))}")


async def test_missing_cookies():
    """
    测试缺少某些 cookie 是否会影响

    对比浏览器完整的 cookie 和我们 API 返回的 cookie
    """
    print("\n" + "="*60)
    print("  对比浏览器 Cookie vs API Cookie")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    # 获取 API cookies
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        await client.get(base_url)
        pub_key_resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
        public_key = pub_key_resp.json().get("data")

        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        login_resp = await client.post(
            f"{base_url}/uic/api/v2/account/login",
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )

        await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            data={"tenantId": "10451"}
        )

        api_cookies = set(k for k, v in client.cookies.items())

    # 浏览器 Cookie（从用户提供的 curl 中提取）
    browser_cookie_names = [
        "dt_expire_cycle", "sysLoginType", "dt_user_id", "dt_username",
        "dt_can_redirect", "dt_tenant_id", "dt_tenant_name", "dt_token",
        "dt_is_tenant_admin", "dt_is_tenant_creator", "dt_product_code",
        "track_rdos", "dt_cookie_time"
    ]

    print("\n浏览器有但 API 没有的 Cookie:")
    for name in browser_cookie_names:
        if name.lower() not in [k.lower() for k in api_cookies]:
            print(f"  - {name}")

    print("\nAPI 有但可能浏览器不需要的 Cookie:")
    for k in api_cookies:
        if k.lower() not in [n.lower() for n in browser_cookie_names]:
            print(f"  - {k}")


async def test_raw_request():
    """
    直接发送最原始的请求 - 不依赖 httpx session
    模拟用户在 Postman 中手动构造请求
    """
    print("\n" + "="*60)
    print("  直接发送原始请求（绕过 session）")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    # 获取 token
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        pub_key_resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
        public_key = pub_key_resp.json().get("data")

        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        login_resp = await client.post(
            f"{base_url}/uic/api/v2/account/login",
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )

        await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            data={"tenantId": "10451"}
        )

        # 获取完整的 cookie
        cookie_str = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])

        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
        cookie_str += f"; sysLoginType=DATABASE; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={dt_cookie_time}; dt_is_tenant_admin=true; dt_is_tenant_creator=true"

    print(f"\n使用的 Cookie: {cookie_str[:300]}...")

    # 直接发送请求
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/api/rdos/common/project/createProject",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json",
                "Cookie": cookie_str,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Host": "shuzhan62-online-test.k8s.dtstack.cn"
            },
            content=json.dumps({
                "projectName": "test_raw_request",
                "projectAlias": "test_raw_request",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )

        print(f"响应: {resp.status_code}")
        print(f"内容: {resp.text}")


if __name__ == "__main__":
    asyncio.run(test_with_sysLoginType())
    asyncio.run(test_missing_cookies())
    asyncio.run(test_raw_request())