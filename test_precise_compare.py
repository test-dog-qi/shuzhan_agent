"""
精确对比浏览器 curl 和我们的请求
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def precise_test():
    """
    精确模拟浏览器请求
    """
    print("="*60)
    print("  精确模拟浏览器请求")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    # 1. 先访问主页建立初始 session
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
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
        public_key = pub_key_resp.json().get("data")

        # 3. SM2 加密密码
        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        # 4. 登录 - 使用与浏览器完全相同的请求头
        login_resp = await client.post(
            f"{base_url}/uic/api/v2/account/login",
            headers={
                "Accept": "application/json, text/plain, */*",
                "X-Custom-Header": "dtuic",
                "Referer": f"{base_url}/",
                "Origin": base_url,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "username": username,
                "password": encrypted_password,
                "verify_code": "1",
                "key": "1"
            }
        )
        print(f"登录响应: {login_resp.status_code}")
        print(f"登录后 cookies: {dict(client.cookies)}")

        # 5. 切换租户
        switch_resp = await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            headers={
                "Accept": "*/*",
                "Origin": base_url,
                "Referer": f"{base_url}/publicService/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            },
            data={"tenantId": "10451"}
        )
        print(f"切换租户: {switch_resp.status_code}")
        print(f"切换后 cookies: {dict(client.cookies)}")

        # 6. 构建完整 cookie 字符串
        cookie_parts = []
        for k, v in client.cookies.items():
            cookie_parts.append(f"{k}={v}")

        # 添加可能缺失的
        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
        cookie_parts.extend([
            "dt_expire_cycle=0",
            "track_rdos=true",
            "dt_product_code=RDOS",
            f"dt_cookie_time={dt_cookie_time}",
            "dt_is_tenant_admin=true",
            "dt_is_tenant_creator=true"
        ])

        full_cookie = "; ".join(cookie_parts)
        print(f"\n完整 cookie ({len(full_cookie)} 字符):")
        print(f"包含的 key: {[p.split('=')[0] for p in cookie_parts]}")

        # 7. 测试创建项目 - 使用与浏览器完全相同的请求头
        print(f"\n--- 测试创建项目 ---")
        create_resp = await client.post(
            f"{base_url}/api/rdos/common/project/createProject",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",  # 浏览器用的是这个
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Referer": f"{base_url}/",
                "Origin": base_url,
                "Cookie": full_cookie
            },
            content=json.dumps({
                "projectName": "test_precise",
                "projectAlias": "test_precise",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )
        result = create_resp.json()
        print(f"创建结果: {result}")


if __name__ == "__main__":
    asyncio.run(precise_test())