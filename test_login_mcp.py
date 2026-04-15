"""测试LoginMCP服务器 - 调试cookie获取问题"""

import asyncio
import json
import os
import sys

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def test_login_flow():
    """完整测试数栈登录流程"""
    print("=" * 60)
    print("数栈登录流程测试")
    print("=" * 60)

    username = os.getenv("DATASTACK_USERNAME")
    password = os.getenv("DATASTACK_PASSWORD")
    base_url = "http://shuzhan62-online-test.k8s.dtstack.cn"

    if not username or not password:
        print("❌ 请配置 DATASTACK_USERNAME 和 DATASTACK_PASSWORD")
        return

    print(f"\n[1] 登录信息:")
    print(f"    用户名: {username}")
    print(f"    密码: {'已设置'}")
    print(f"    基础URL: {base_url}")

    # 1. 先获取公钥
    print(f"\n[2] 获取公钥...")
    pub_key_url = f"{base_url}/uic/api/v2/account/login/get-publi-key"

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # 第一次请求 - 获取公钥
            resp1 = await client.get(
                pub_key_url,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "X-Custom-Header": "dtuic",
                    "Referer": f"{base_url}/",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
                }
            )

            print(f"    状态码: {resp1.status_code}")

            # 提取session cookie
            session_id = None
            for key, value in resp1.headers.items():
                if key.lower() == 'set-cookie' and 'DT_SESSION_ID' in value:
                    for part in value.split(';'):
                        if 'DT_SESSION_ID' in part:
                            session_id = part.split('=')[1].strip()
                            break

            print(f"    提取的 DT_SESSION_ID: {session_id}")

            pub_key_data = resp1.json()
            print(f"    公钥响应: {json.dumps(pub_key_data, ensure_ascii=False)}")

            pub_key_hex = pub_key_data.get('data')
            if not pub_key_hex:
                print(f"    ❌ 公钥数据为空")
                return

            print(f"    公钥 (hex): {pub_key_hex[:50]}...")

            # 2. 使用gmssl加密密码
            print(f"\n[3] 密码SM2加密...")

            try:
                from gmssl import sm2

                # SM2加密 - 公钥是130字符的hex字符串(65字节未压缩格式)
                # gmssl的CryptSM2需要(16进制公钥, 16进制私钥)
                # 由于是加密，私钥可以为空

                sm2_crypt = sm2.CryptSM2(
                    public_key=pub_key_hex,  # 130字符hex
                    private_key=""          # 空表示只用于加密
                )

                # 加密密码 - 需要bytes
                password_encrypted = sm2_crypt.encrypt(password.encode('utf-8'))
                # gmssl返回bytes，需要hex编码
                password_encrypted_hex = f'04{password_encrypted.hex()}'
                print(f"    加密后密码 (hex): {password_encrypted_hex}")
                print(f"    加密后密码长度: {len(password_encrypted_hex)}")

            except Exception as e:
                print(f"    ❌ SM2加密失败: {e}")
                import traceback
                traceback.print_exc()
                return

            # 3. 发送登录请求
            print(f"\n[4] 发送登录请求...")

            # 构造cookies
            cookies_dict = {"dt_expire_cycle": "0"}
            if session_id:
                cookies_dict["DT_SESSION_ID"] = session_id

            login_url = f"{base_url}/uic/api/v2/account/login"
            # password_encrypted_hex = "0497bbc95baa5f1dedd52d6d31bde5ef8b4d4f2fee14aa833b808ab8a3291ac3ac045e7ccd139276f7754b6fc7e8e305d4601d45523ab1979b86e69220699ab1693f09d32d049cc0a5b6c12258c98d999d3a90e846432082155798cbcac83d99c087931178896c813ff59ec2"
            resp2 = await client.post(
                login_url,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "X-Custom-Header": "dtuic",
                    "Referer": f"{base_url}/",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                    "Origin": base_url
                },
                content=f"username={username}&password={password_encrypted_hex}&verify_code=1&key=1",
                cookies=cookies_dict
            )

            print(f"    状态码: {resp2.status_code}")

            # 检查响应头中的cookie
            print(f"\n[5] 检查登录响应:")
            print(f"    response.cookies: {dict(resp2.cookies)}")

            set_cookies = []
            for key, value in resp2.headers.items():
                if key.lower() == 'set-cookie':
                    set_cookies.append(value)
                    print(f"    Set-Cookie: {value}")

            try:
                login_data = resp2.json()
                print(f"    登录响应: {json.dumps(login_data, ensure_ascii=False, indent=2)}")
            except:
                print(f"    登录响应(原始): {resp2.text[:500]}")

            # 4. 验证cookie
            if set_cookies or resp2.cookies:
                print(f"\n[6] ✅ 登录成功，获取到Cookie!")
                final_cookie = "; ".join([f"{k}={v}" for k, v in resp2.cookies.items()])
                print(f"    Cookie: {final_cookie}")
            else:
                print(f"\n[6] ❌ 未获取到Cookie")
                print(f"    可能原因: verify_code或key参数不正确")

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("数栈登录调试")
    print("=" * 60)

    await test_login_flow()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
