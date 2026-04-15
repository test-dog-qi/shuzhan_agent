"""
Login MCP服务器 - 基于FastMCP

提供登录相关工具：
- LoginTool: API登录（支持多环境）
- GetAuthToken: 获取认证令牌
- Logout: 登出

可以作为独立MCP服务器运行，也可以通过MCPToolProxy统一调用
"""

import os
import json
import asyncio
import base64
from typing import Any, Dict, Optional
import httpx
from dotenv import load_dotenv

from fastmcp import FastMCP
load_dotenv()
# 创建FastMCP服务器
login_mcp = FastMCP("Login_MCP")

# 多环境登录URL配置
ENVIRONMENT_LOGIN_URLS = {
    "62": "http://shuzhan62-online-test.k8s.dtstack.cn",
    "63": "http://shuzhan63-zdxx.k8s.dtstack.cn",
    "test": "http://shuzhan62-online-test.k8s.dtstack.cn",
    "default": "http://shuzhan62-online-test.k8s.dtstack.cn",
    "生产": "https://shuzhan-prod.k8s.dtstack.cn",
}

# 登录API路径
LOGIN_API_PATH = "/uic/api/v2/account/login"
PUB_KEY_API_PATH = "/uic/api/v2/account/login/get-publi-key"
TENANT_SWITCH_API_PATH = "/api/publicService/userCenter/account/user/switch-tenant"

def sm2_encrypt(public_key: str, password: str) -> str:
    """
    使用gmssl进行SM2加密

    Args:
        public_key: 公钥(hex字符串，130字符)
        password: 原始密码

    Returns:
        加密后的密码(hex字符串)
    """
    from gmssl import sm2

    sm2_crypt = sm2.CryptSM2(
        public_key=public_key,
        private_key=""
    )

    encrypted = sm2_crypt.encrypt(password.encode('utf-8'))
    # Java实现返回的结果前面有04前缀
    return f'04{encrypted.hex()}'


def get_login_url(environment_name: str = "default") -> str:
    """获取指定环境的登录URL"""
    # 1. 先检查环境变量
    env_url = os.getenv(f"DATASTACK_{environment_name.upper()}_URL")
    if env_url:
        return env_url

    # 2. 检查预配置的环境URL
    if environment_name in ENVIRONMENT_LOGIN_URLS:
        return ENVIRONMENT_LOGIN_URLS[environment_name]

    # 3. 使用默认URL
    return os.getenv("DATASTACK_BASE_URL", ENVIRONMENT_LOGIN_URLS["default"])


def set_auth_token(environment_name: str, token: str) -> None:
    """设置认证令牌"""
    os.environ[f"DATASTACK_{environment_name.upper()}_TOKEN"] = token


def get_auth_token(environment_name: str = "default") -> Optional[str]:
    """获取认证令牌"""
    return os.getenv(f"DATASTACK_{environment_name.upper()}_TOKEN")


def _generate_dt_cookie_time() -> str:
    """生成dt_cookie_time字段，格式: YYYY-MM-DD+HH%3AMM%3ASS (URL编码)"""
    from datetime import datetime
    now = datetime.now()
    # 格式: 2026-04-10+14%3A24%3A34
    # + 替换空格，%3A 替换 :
    time_str = now.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "+").replace(":", "%3A")
    return time_str


def _keep_first_dt_token(cookie_str: str) -> str:
    """
    只保留 cookie 字符串中的第一个 dt_token

    switch-tenant 接口会返回多个 dt_token，第一个用于接口调用，后续的是其他用途
    """
    if not cookie_str or "dt_token=" not in cookie_str:
        return cookie_str

    # 分割 cookie 字符串
    parts = []
    current = cookie_str
    while "dt_token=" in current:
        idx = current.find("dt_token=")
        # 找到这个 dt_token 的结束位置（下一个分号或字符串结尾）
        rest = current[idx + len("dt_token="):]
        # 找到分号或逗号分隔的位置
        end_idx = len(rest)
        for sep in [";", ",", " "]:
            if sep in rest:
                e = rest.find(sep)
                if e < end_idx:
                    end_idx = e
        first_token = current[:idx + len("dt_token=") + end_idx]
        parts.append(first_token)
        current = current[idx + len("dt_token=") + end_idx:]

    # 只保留第一个 dt_token
    if len(parts) > 1:
        # 重建 cookie 字符串，用空字符串替换后续的 dt_token
        first_part = parts[0]
        rest = cookie_str[len(first_part):]
        # 移除后续的 dt_token
        while "dt_token=" in rest:
            idx = rest.find("dt_token=")
            rest_part = rest[idx + len("dt_token="):]
            end_idx = len(rest_part)
            for sep in [";", ",", " "]:
                if sep in rest_part:
                    e = rest_part.find(sep)
                    if e < end_idx:
                        end_idx = e
            rest = rest[idx + len("dt_token=") + end_idx:]
        return first_part + ";" + rest

    return cookie_str


def _build_cookie_from_response(response: httpx.Response) -> str:
    """从响应中提取所有cookie并构建cookie字符串"""
    cookie_parts = []

    # 方法1: 从 response.cookies.items() 提取
    for key, value in response.cookies.items():
        cookie_parts.append(f"{key}={value}")

    # 方法2: 从 Set-Cookie 头提取（httpx.cookies 可能遗漏部分cookie）
    set_cookie_headers = response.headers.get_list("set-cookie")
    for cookie_header in set_cookie_headers:
        # 解析 Set-Cookie 头，提取 name=value 部分
        if cookie_header:
            parts = cookie_header.split(";")
            if parts:
                name_value = parts[0].strip()
                # 检查是否已存在（用于去重）
                if name_value and not any(name_value.startswith(p.split("=")[0] + "=") for p in cookie_parts):
                    cookie_parts.append(name_value)

    # 方法3: 硬编码cookie（这些由前端JavaScript设置）
    hardcoded_cookies = [
        "dt_expire_cycle=0",
        "track_rdos=true",
        "dt_product_code=RDOS",
        f"dt_cookie_time={_generate_dt_cookie_time()}",
    ]
    for hc in hardcoded_cookies:
        key = hc.split("=")[0]
        if not any(p.startswith(key + "=") for p in cookie_parts):
            cookie_parts.append(hc)

    return "; ".join(cookie_parts)


def merge_cookies(cookie_strs: list) -> str:
    """合并多个cookie字符串，去除重复的cookie项

    Args:
        cookie_strs: cookie字符串列表

    Returns:
        合并后的cookie字符串
    """
    cookie_dict = {}

    for cookie_str in cookie_strs:
        if not cookie_str:
            continue
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            key = part.split("=")[0]
            # 后面的值覆盖前面的值
            cookie_dict[key] = part

    return "; ".join(cookie_dict.values())


@login_mcp.tool()
async def LoginTool(
    environment_name: str = "default",
    username: str = None,
    password: str = None,
    base_url: str = None
) -> str:
    """
    数栈平台API登录工具

    支持多环境登录、SM2密码加密、cookie自动获取

    Args:
        environment_name: 环境名称（如 "62"、"63"、"test"、"生产"）
        username: 用户名（可选，如果已保存凭证则无需提供）
        password: 密码（可选，如果已保存凭证则无需提供）
        base_url: 登录URL（可选，将根据environment_name自动选择）

    Returns:
        JSON格式的登录结果
    """
    print("===== LoginTool 被调用 =====")
    print(f"environment_name={environment_name}, username={username}, base_url={base_url}")
    # 1. 确定登录URL和环境名
    if not base_url:
        base_url = get_login_url(environment_name)
    else:
        base_url = base_url.rstrip("/")

    # 如果环境名是默认但URL包含环境标识，自动推断
    if environment_name == "default":
        if "63" in base_url:
            environment_name = "63"
        elif "62" in base_url:
            environment_name = "62"

    # 2. 如果没有提供用户名密码，尝试从环境变量获取
    if not username:
        username = os.getenv("DATASTACK_USERNAME")
    if not password:
        password = os.getenv("DATASTACK_PASSWORD")

    if not username or not password:
        return json.dumps({
            "success": False,
            "message": "请提供用户名和密码，或配置 DATASTACK_USERNAME 和 DATASTACK_PASSWORD 环境变量",
            "environment_name": environment_name,
            "base_url": base_url
        })

    # 3. 获取公钥
    pub_key_url = f"{base_url}{PUB_KEY_API_PATH}"
    max_retries = 3
    last_error = ""

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                # 获取公钥（使用同一个 client，保持 cookie 一致性）
                pub_key_resp = await client.get(
                    pub_key_url,
                    headers={
                        "Accept": "application/json, text/plain, */*",
                        "X-Custom-Header": "dtuic",
                        "Referer": f"{base_url}/",
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
                    }
                )

                pub_key_data = pub_key_resp.json()
                if pub_key_data.get("code") != 1:
                    last_error = f"获取公钥失败: {pub_key_data.get('message', 'Unknown')}"
                    continue

                public_key = pub_key_data.get("data")
                if not public_key:
                    last_error = "公钥数据为空"
                    continue

                # 保存登录前的 cookie（用于后续请求）
                pre_login_cookies = dict(client.cookies)

                # 4. SM2加密密码
                try:
                    encrypted_password = sm2_encrypt(public_key, password)
                except Exception as e:
                    return json.dumps({
                        "success": False,
                        "message": f"密码加密失败: {str(e)}",
                        "environment_name": environment_name
                    })

                # 5. 发送登录请求
                login_url = f"{base_url}{LOGIN_API_PATH}"
                login_resp = await client.post(
                    login_url,
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

                login_data = login_resp.json()
                code = login_data.get("code", -1)

                if code == 1 and login_data.get("success"):
                    # 登录成功，获取初始cookie
                    login_cookie = _build_cookie_from_response(login_resp)

                    # 调用租户切换接口获取完整cookie
                    full_cookie, switch_cookie = await _switch_tenant_and_get_full_cookie(
                        client, base_url, login_cookie
                    )

                    # 保存cookie到环境变量
                    if full_cookie:
                        os.environ[f"DATASTACK_{environment_name.upper()}_COOKIE"] = full_cookie

                    # 保存凭证到本地文件
                    _save_credentials_to_file(username, password, base_url, environment_name, None, full_cookie or login_cookie)

                    return json.dumps({
                        "success": True,
                        "message": f"登录成功（环境: {environment_name}）",
                        "cookie": full_cookie or login_cookie,
                        "switch_cookie": switch_cookie,  # 租户切换返回的原始cookie
                        "user_info": {
                            "username": username,
                            "environment_name": environment_name,
                            "base_url": base_url
                        }
                    })
                else:
                    last_error = login_data.get("message", "登录失败")
                    break

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP错误 {e.response.status_code}"
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue

    return json.dumps({
        "success": False,
        "message": f"登录失败: {last_error}",
        "environment_name": environment_name
    })


@login_mcp.tool()
async def GetAuthToken(
    environment_name: str = "default"
) -> str:
    """
    获取指定环境的认证令牌

    Args:
        environment_name: 环境名称

    Returns:
        JSON格式的令牌信息
    """
    token = get_auth_token(environment_name)
    if token:
        return json.dumps({
            "success": True,
            "token": token,
            "environment_name": environment_name
        })
    else:
        return json.dumps({
            "success": False,
            "message": f"未找到环境 {environment_name} 的令牌，请先登录"
        })


@login_mcp.tool()
async def Logout(
    environment_name: str = "default"
) -> str:
    """
    登出指定环境（清除令牌）

    Args:
        environment_name: 环境名称

    Returns:
        JSON格式的登出结果
    """
    token_env_key = f"DATASTACK_{environment_name.upper()}_TOKEN"
    cookie_env_key = f"DATASTACK_{environment_name.upper()}_COOKIE"
    if token_env_key in os.environ:
        del os.environ[token_env_key]
    if cookie_env_key in os.environ:
        del os.environ[cookie_env_key]

    return json.dumps({
        "success": True,
        "message": f"已登出环境 {environment_name}"
    })


def _save_credentials_to_file(
    username: str,
    password: str,
    base_url: str,
    environment_name: str,
    token: str = None,
    cookie: str = None
) -> None:
    """保存凭证到本地文件"""
    try:
        creds_dir = os.path.expanduser("~/.shuzhan_agent")
        os.makedirs(creds_dir, exist_ok=True)
        creds_file = os.path.join(creds_dir, "credentials.json")

        existing = {}
        if os.path.exists(creds_file):
            try:
                with open(creds_file, "r") as f:
                    existing = json.load(f)
            except:
                pass

        existing[environment_name] = {
            "username": username,
            "password": password,
            "base_url": base_url,
            "token": token,
            "cookie": cookie
        }

        with open(creds_file, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        pass


async def _switch_tenant_and_get_full_cookie(
    client: httpx.AsyncClient,
    base_url: str,
    login_cookie: str
) -> tuple:
    """
    调用租户切换接口获取完整cookie

    Args:
        client: httpx客户端
        base_url: 基础URL
        login_cookie: 登录返回的cookie

    Returns:
        (full_cookie, switch_cookie) 元组
    """
    import sys
    sys.stderr.write("===== _switch_tenant_and_get_full_cookie 被调用 =====\n")
    sys.stderr.flush()
    try:
        switch_url = f"{base_url}{TENANT_SWITCH_API_PATH}"
        sys.stderr.write(f"===== 租户切换请求 =====\n")
        sys.stderr.write(f"url: {switch_url}\n")
        sys.stderr.write(f"login_cookie: {login_cookie}\n")
        sys.stderr.flush()
        switch_resp = await client.post(
            switch_url,
            headers={
                "Accept": "*/*",
                "Cookie": login_cookie,
                "Origin": base_url,
                "Referer": f"{base_url}/publicService/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            },
            data={"tenantId": "1"}  # 使用 data 而不是 content
        )
        sys.stderr.write(f"===== 租户切换响应状态: {switch_resp.status_code} =====\n")
        sys.stderr.write(f"switch_resp.headers: {dict(switch_resp.headers)}\n")
        sys.stderr.flush()

        # 直接从 Set-Cookie 头提取 cookie
        # 重要：对于 dt_token，只取第一个（后续的是其他用途）
        switch_cookie_parts = []
        seen_cookie_names = set()  # 用于去重，但对于 dt_token 只取第一个
        first_dt_token_found = False

        for cookie_header in switch_resp.headers.get_list("set-cookie"):
            if cookie_header:
                # 解析 Set-Cookie 头，提取 name=value 部分
                parts = cookie_header.split(";")
                if parts and parts[0].strip():
                    name_value = parts[0].strip()
                    cookie_name = name_value.split("=")[0] if "=" in name_value else ""

                    # 对于 dt_token，只取第一个
                    if cookie_name == "dt_token":
                        if first_dt_token_found:
                            # 跳过后续的 dt_token
                            sys.stderr.write(f"===== 跳过后续 dt_token =====\n")
                            sys.stderr.flush()
                            continue
                        first_dt_token_found = True

                    # 检查是否已存在（用于去重，但 dt_token 已经特殊处理）
                    if cookie_name not in seen_cookie_names:
                        switch_cookie_parts.append(name_value)
                        seen_cookie_names.add(cookie_name)

        switch_cookie = "; ".join(switch_cookie_parts)

        # 添加硬编码 cookie
        switch_cookie += f"; dt_expire_cycle=0; track_rdos=true; dt_product_code=RDOS; dt_cookie_time={_generate_dt_cookie_time()}"

        sys.stderr.write(f"===== 租户切换返回的cookie =====\n")
        sys.stderr.write(f"switch_cookie: {switch_cookie}\n")
        sys.stderr.flush()

        # 合并登录cookie和租户切换cookie
        full_cookie = merge_cookies([login_cookie, switch_cookie])

        return full_cookie, switch_cookie

    except Exception as e:
        sys.stderr.write(f"租户切换失败: {e}\n")
        sys.stderr.flush()
        # 租户切换失败时返回登录cookie
        return login_cookie, ""


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Login MCP Server")
    parser.add_argument("--transport", "-t", default="stdio", choices=["stdio", "http", "sse"],
                        help="Transport mode (default: stdio)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP/SSE transport")
    parser.add_argument("--port", "-p", type=int, default=8081, help="Port for HTTP/SSE transport")

    args = parser.parse_args()

    if args.transport == "http":
        print(f"🚀 Starting HTTP MCP Server on {args.host}:{args.port}")
        login_mcp.run(transport="http", host=args.host, port=args.port)
    elif args.transport == "sse":
        print(f"🚀 Starting SSE MCP Server on {args.host}:{args.port}")
        login_mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        print("🚀 Starting MCP Server (stdio mode)")
        login_mcp.run()
