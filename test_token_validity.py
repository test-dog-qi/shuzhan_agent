"""
测试 dt_token 的有效性 - 对比浏览器环境和直接 API 调用

关键测试：
1. 使用浏览器完整流程登录，获取 cookies 和 dt_token
2. 使用纯 API 流程登录，获取 dt_token
3. 对比两者的 dt_token 差异
4. 验证是否是请求头/顺序问题
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
            # 添加 padding
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            return json.loads(decoded)
    except Exception as e:
        print(f"JWT 解码失败: {e}")
    return {}


async def test_api_login_and_token():
    """纯 API 登录测试"""
    print("="*60)
    print("  步骤1: 纯 API 登录")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # 1. 获取公钥
            pub_key_resp = await client.get(
                f"{base_url}/uic/api/v2/account/login/get-publi-key",
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "X-Custom-Header": "dtuic",
                    "Referer": f"{base_url}/",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
                }
            )
            print(f"获取公钥: {pub_key_resp.status_code}")

            pub_key_data = pub_key_resp.json()
            public_key = pub_key_data.get("data")
            print(f"公钥: {public_key[:50]}...")

            # 保存登录前的 cookie
            pre_login_cookies = dict(client.cookies)

            # 2. SM2 加密密码
            from gmssl import sm2
            sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key="")
            encrypted_password = f'04{sm2_crypt.encrypt(password.encode("utf-8")).hex()}'

            # 3. 登录
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
            print(f"登录: {login_resp.status_code}")

            login_data = login_resp.json()
            print(f"登录响应: {json.dumps(login_data, ensure_ascii=False)[:300]}")

            # 提取 cookie
            cookie_parts = []
            for key, value in login_resp.cookies.items():
                cookie_parts.append(f"{key}={value}")

            login_cookie = "; ".join(cookie_parts)
            print(f"登录 Cookie: {login_cookie[:200]}...")

            # 4. 租户切换
            switch_resp = await client.post(
                f"{base_url}/uic/api/v2/account/user/switch-tenant",
                headers={
                    "Accept": "*/*",
                    "Cookie": login_cookie,
                    "Origin": base_url,
                    "Referer": f"{base_url}/publicService/",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
                },
                data={"tenantId": "1"}
            )
            print(f"租户切换: {switch_resp.status_code}")

            # 合并 cookie
            for key, value in switch_resp.cookies.items():
                cookie_parts.append(f"{key}={value}")

            full_cookie = "; ".join(cookie_parts)

            # 添加 hardcoded cookies
            from datetime import datetime
            dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
            hardcoded = "dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time=" + dt_cookie_time
            full_cookie = merge_cookies([full_cookie, hardcoded])

            # 解码 dt_token
            dt_token_match = None
            for part in cookie_parts:
                if part.startswith("dt_token="):
                    dt_token_match = part.split("=", 1)[1].split(";")[0]
                    break

            if dt_token_match:
                print(f"\ndt_token (API): {dt_token_match[:100]}...")
                payload = decode_jwt_payload(dt_token_match)
                print(f"dt_token payload: {json.dumps(payload, indent=2)}")

            # 5. 测试创建项目
            print("\n--- 测试创建项目 (API cookie) ---")
            create_resp = await client.post(
                f"{base_url}/api/rdos/common/project/createProject",
                headers={
                    "Content-Type": "text/plain;charset=UTF-8",
                    "Accept": "application/json",
                    "Cookie": full_cookie
                },
                content=json.dumps({
                    "projectName": "test_api_token_0407",
                    "projectAlias": "test_api_token_0407",
                    "projectEngineList": [{"createModel": 0, "engineType": 1}],
                    "isAllowDownload": 1,
                    "scheduleStatus": 0,
                    "projectOwnerId": "1"
                })
            )
            print(f"创建项目响应: {create_resp.status_code}")
            print(f"响应内容: {create_resp.text[:500]}")

            return full_cookie

    except Exception as e:
        print(f"API 登录测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


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


async def test_exact_curl_request():
    """
    测试模拟浏览器复制的 curl 请求

    用户说把接口 curl 复制到 postman 会失败，
    关键差异可能是：
    1. 浏览器复制的 curl 包含所有请求头
    2. 浏览器请求时已经建立了完整的 session context
    """
    print("\n" + "="*60)
    print("  步骤2: 模拟完整浏览器请求流程")
    print("="*60)

    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"
    username = os.getenv("DATASTACK_USERNAME", "admin@dtstack.com")
    password = os.getenv("DATASTACK_PASSWORD", "DrpEco_2020")

    # 首先访问登录页面获取初始 cookies
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 1. 先访问主页，获取初始 cookies
        print("\n1. 访问主页...")
        home_resp = await client.get(base_url)
        print(f"   主页状态: {home_resp.status_code}")
        print(f"   设置的 cookies: {dict(client.cookies)}")

        # 2. 获取公钥（保持 session）
        print("\n2. 获取公钥...")
        pub_key_resp = await client.get(
            f"{base_url}/uic/api/v2/account/login/get-publi-key",
            headers={
                "Accept": "application/json, text/plain, */*",
                "X-Custom-Header": "dtuic",
                "Referer": f"{base_url}/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive"
            }
        )
        print(f"   状态: {pub_key_resp.status_code}")

        pub_key_data = pub_key_resp.json()
        public_key = pub_key_data.get("data")

        # 3. 登录
        print("\n3. 执行登录...")

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
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "username": username,
                "password": encrypted_password,
                "verify_code": "1",
                "key": "1"
            }
        )
        print(f"   登录状态: {login_resp.status_code}")
        print(f"   登录响应: {login_resp.text[:200]}")

        # 获取登录后的 cookies
        login_cookie = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])
        print(f"   Session cookies: {login_cookie[:200]}...")

        # 4. 租户切换
        print("\n4. 切换租户...")
        switch_resp = await client.post(
            f"{base_url}/uic/api/v2/account/user/switch-tenant",
            headers={
                "Accept": "*/*",
                "Referer": f"{base_url}/publicService/",
                "Origin": base_url,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            },
            data={"tenantId": "1"}
        )
        print(f"   切换状态: {switch_resp.status_code}")

        full_cookie = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])

        # 添加 hardcoded
        from datetime import datetime
        dt_cookie_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
        full_cookie = merge_cookies([full_cookie, f"dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={dt_cookie_time}"])

        # 解码 dt_token
        for part in full_cookie.split(";"):
            part = part.strip()
            if part.startswith("dt_token="):
                dt_token = part.split("=", 1)[1]
                print(f"\n   dt_token: {dt_token[:80]}...")
                payload = decode_jwt_payload(dt_token)
                print(f"   payload: {json.dumps(payload, indent=2)}")
                break

        # 5. 测试创建项目
        print("\n5. 测试创建项目...")
        create_resp = await client.post(
            f"{base_url}/api/rdos/common/project/createProject",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Accept": "application/json",
                "Referer": f"{base_url}/",
                "Origin": base_url
            },
            content=json.dumps({
                "projectName": "test_session_0407",
                "projectAlias": "test_session_0407",
                "projectEngineList": [{"createModel": 0, "engineType": 1}],
                "isAllowDownload": 1,
                "scheduleStatus": 0,
                "projectOwnerId": "1"
            })
        )
        print(f"   响应: {create_resp.status_code}")
        print(f"   内容: {create_resp.text[:500]}")


async def main():
    print("="*60)
    print("  dt_token 有效性测试")
    print("  目标：分析为什么 Postman 调用会报'无此用户'")
    print("="*60)

    # 1. 纯 API 测试
    cookie = await test_api_login_and_token()

    # 2. 模拟完整浏览器请求
    await test_exact_curl_request()


if __name__ == "__main__":
    asyncio.run(main())