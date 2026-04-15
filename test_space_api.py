"""
测试 rdosUserSpace API

可能需要先调用某个 space API 来建立用户与项目的关联
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_space_related_apis():
    """测试 space 相关的 API"""
    print("="*60)
    print("  测试 Space 相关 API")
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

        # 切换租户
        await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            data={"tenantId": "10451"}
        )

        cookie = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])
        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
        cookie += f"; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={dt_cookie_time}; dt_is_tenant_admin=true; dt_is_tenant_creator=true"

        # 测试 space 相关的 API
        apis = [
            # Space 列表
            "/api/rdos/common/rdosUserSpace/list",
            "/api/rdos/rdosUserSpace/list",
            "/rdos/api/rdosUserSpace/list",
            # Space 详情
            "/api/rdos/common/rdosUserSpace/getUserSpaceByToken",
            "/api/rdos/common/space/getByToken",
            # 用户信息
            "/api/rdos/common/user/info",
            "/api/rdos/common/user/getUserInfo",
        ]

        for path in apis:
            print(f"\nGET {path}")
            try:
                resp = await client.get(
                    f"{base_url}{path}",
                    headers={
                        "Content-Type": "text/plain;charset=UTF-8",
                        "Cookie": cookie,
                        "Accept": "application/json"
                    }
                )
                print(f"   {resp.status_code} - {resp.text[:300]}")
            except Exception as e:
                print(f"   Error: {e}")


async def test_login_with_dtstack_cookie():
    """
    测试：如果直接在 Cookie 中传入 dtstack 用户的特定 cookie

    某些系统可能需要预先存在的 dtstack_session 或类似的值
    """
    print("\n" + "="*60)
    print("  测试预存的 dtstack_session cookie")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 1. 先访问主页获取初始 cookie
        home_resp = await client.get(base_url)
        print(f"主页: {home_resp.status_code}")
        initial_cookies = dict(client.cookies)
        print(f"初始 cookies: {initial_cookies}")

        # 2. 登录
        pub_key_resp = await client.get(f"{base_url}/uic/api/v2/account/login/get-publi-key")
        public_key = pub_key_resp.json().get("data")

        from gmssl import sm2
        sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
        encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

        await client.post(
            f"{base_url}/uic/api/v2/account/login",
            data={"username": username, "password": encrypted_password, "verify_code": "1", "key": "1"}
        )

        # 切换租户
        await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            data={"tenantId": "10451"}
        )

        after_login_cookies = dict(client.cookies)
        print(f"\n登录后 cookies: {after_login_cookies}")

        # 3. 构建包含所有可能 cookie 的完整字符串
        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")

        # 使用 httpx 的 cookie 格式
        full_cookie = "; ".join([f"{k}={v}" for k, v in after_login_cookies.items()])
        full_cookie += f"; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={dt_cookie_time}; dt_is_tenant_admin=true; dt_is_tenant_creator=true"

        print(f"\n完整 cookie 长度: {len(full_cookie)}")
        print(f"Cookie 包含的 key: {[p.split('=')[0] for p in full_cookie.split('; ')]}")

        # 4. 测试创建项目
        print("\n--- 测试创建项目 ---")
        resp = await client.post(
            f"{base_url}/api/rdos/common/project/createProject",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Cookie": full_cookie,
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            },
            content=json.dumps({
                "projectName": "test_complete_cookie",
                "projectAlias": "test_complete_cookie",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )
        print(f"响应: {resp.status_code}")
        print(f"内容: {resp.text}")


if __name__ == "__main__":
    asyncio.run(test_space_related_apis())
    asyncio.run(test_login_with_dtstack_cookie())