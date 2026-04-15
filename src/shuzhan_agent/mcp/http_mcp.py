"""
HTTP MCP服务器 - 基于FastMCP

提供四个HTTP工具：POST、GET、PUT、DELETE
用于调用数栈平台API

可以作为独立MCP服务器运行，也可以通过MCPToolProxy统一调用
"""

import os
import json
import base64
from typing import Any, Dict, Optional
import httpx

from fastmcp import FastMCP

# 创建FastMCP服务器
http_mcp = FastMCP("HTTP_MCP")

# 默认配置
DEFAULT_BASE_URL = os.getenv("DATASTACK_BASE_URL", "http://shuzhan62-online-test.k8s.dtstack.cn")
DEFAULT_TIMEOUT = 30


def get_base_url() -> str:
    """获取基础URL"""
    return os.getenv("DATASTACK_BASE_URL", DEFAULT_BASE_URL)


def _load_token_from_file(environment_name: str) -> str:
    """从凭证文件加载token"""
    try:
        creds_file = os.path.expanduser("~/.shuzhan_agent/credentials.json")
        if os.path.exists(creds_file):
            with open(creds_file, "r") as f:
                creds = json.load(f)
            return creds.get(environment_name, {}).get("token")
    except Exception:
        pass
    return None


def get_auth_headers(environment_name: str = "default") -> Dict[str, str]:
    """获取认证头"""
    headers = {}

    # 1. 优先使用环境变量中的token
    token = os.getenv(f"DATASTACK_{environment_name.upper()}_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        return headers

    # 2. 从凭证文件读取token（stdio模式下子进程无法共享环境变量）
    token = _load_token_from_file(environment_name)
    if token:
        headers["Authorization"] = f"Bearer {token}"
        return headers

    # 3. 使用Basic Auth
    username = os.getenv("DATASTACK_USERNAME")
    password = os.getenv("DATASTACK_PASSWORD")

    if username and password:
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"

    return headers


def _build_auth_headers(environment: str, token: str = None, cookies: str = None) -> Dict[str, str]:
    """构建认证头

    优先级：1. 直接传入的cookies 2. 直接传入的token 3. 环境变量/文件中的token 4. Basic Auth
    """
    auth_headers = {}

    # 1. cookies优先（登录后返回的cookie）
    if cookies:
        auth_headers["Cookie"] = cookies
        return auth_headers

    # 2. token
    if token:
        auth_headers["Authorization"] = f"Bearer {token}"
        return auth_headers

    # 3. 回退到环境变量/文件
    headers = get_auth_headers(environment)
    return headers


def _load_cookie_from_file(environment_name: str) -> Optional[str]:
    """从凭证文件加载cookie"""
    try:
        creds_file = os.path.expanduser("~/.shuzhan_agent/credentials.json")
        if os.path.exists(creds_file):
            with open(creds_file, "r") as f:
                creds = json.load(f)
            return creds.get(environment_name, {}).get("cookie")
    except Exception:
        pass
    return None


@http_mcp.tool()
async def GET(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    environment: str = "default",
    token: Optional[str] = None,
    cookies: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> str:
    """
    发送GET请求

    Args:
        url: 请求URL（如果填写绝对URL则直接使用，否则拼接base_url）
        params: 查询参数
        headers: 请求头
        environment: 环境名称（用于认证）
        token: 认证令牌（优先于environment读取的token）
        cookies: 认证cookie（优先于token）
        timeout: 超时时间（秒）

    Returns:
        JSON格式的响应内容
    """
    base_url = get_base_url()

    # 拼接URL
    if not url.startswith("http"):
        full_url = f"{base_url.rstrip('/')}/{url.lstrip('/')}"
    else:
        full_url = url

    # 构建认证头 - cookies优先
    if not cookies:
        cookies = os.getenv(f"DATASTACK_{environment.upper()}_COOKIE")
        if not cookies:
            cookies = _load_cookie_from_file(environment)
    auth_headers = _build_auth_headers(environment, token, cookies)
    if headers:
        auth_headers.update(headers)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(full_url, params=params, headers=auth_headers)
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        return f"HTTP错误 {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"请求失败: {str(e)}"


@http_mcp.tool()
async def POST(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    environment: str = "default",
    token: Optional[str] = None,
    cookies: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> str:
    """
    发送POST请求

    Args:
        url: 请求URL（如果填写绝对URL则直接使用，否则拼接base_url）
        params: 查询参数
        json: JSON请求体
        headers: 请求头
        environment: 环境名称（用于认证）
        token: 认证令牌（优先于environment读取的token）
        cookies: 认证cookie（优先于token）
        timeout: 超时时间（秒）

    Returns:
        JSON格式的响应内容
    """
    base_url = get_base_url()

    # 拼接URL
    if not url.startswith("http"):
        full_url = f"{base_url.rstrip('/')}/{url.lstrip('/')}"
    else:
        full_url = url

    # 构建认证头 - cookies优先
    if not cookies:
        cookies = os.getenv(f"DATASTACK_{environment.upper()}_COOKIE")
        if not cookies:
            cookies = _load_cookie_from_file(environment)
    auth_headers = _build_auth_headers(environment, token, cookies)
    if headers:
        auth_headers.update(headers)

    # 调试输出
    print(f"[HTTP POST] url={full_url}")
    print(f"[HTTP POST] cookies={cookies[:100] if cookies else 'None'}...")
    print(f"[HTTP POST] headers={auth_headers}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(full_url, params=params, json=json, headers=auth_headers)
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        return f"HTTP错误 {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"请求失败: {str(e)}"


@http_mcp.tool()
async def PUT(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    environment: str = "default",
    token: Optional[str] = None,
    cookies: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> str:
    """
    发送PUT请求

    Args:
        url: 请求URL（如果填写绝对URL则直接使用，否则拼接base_url）
        params: 查询参数
        json: JSON请求体
        headers: 请求头
        environment: 环境名称（用于认证）
        token: 认证令牌（优先于environment读取的token）
        cookies: 认证cookie（优先于token）
        timeout: 超时时间（秒）

    Returns:
        JSON格式的响应内容
    """
    base_url = get_base_url()

    # 拼接URL
    if not url.startswith("http"):
        full_url = f"{base_url.rstrip('/')}/{url.lstrip('/')}"
    else:
        full_url = url

    # 构建认证头 - cookies优先
    if not cookies:
        cookies = os.getenv(f"DATASTACK_{environment.upper()}_COOKIE")
        if not cookies:
            cookies = _load_cookie_from_file(environment)
    auth_headers = _build_auth_headers(environment, token, cookies)
    if headers:
        auth_headers.update(headers)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.put(full_url, params=params, json=json, headers=auth_headers)
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        return f"HTTP错误 {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"请求失败: {str(e)}"


@http_mcp.tool()
async def DELETE(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    environment: str = "default",
    token: Optional[str] = None,
    cookies: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> str:
    """
    发送DELETE请求

    Args:
        url: 请求URL（如果填写绝对URL则直接使用，否则拼接base_url）
        params: 查询参数
        headers: 请求头
        environment: 环境名称（用于认证）
        token: 认证令牌（优先于environment读取的token）
        cookies: 认证cookie（优先于token）
        timeout: 超时时间（秒）

    Returns:
        JSON格式的响应内容
    """
    base_url = get_base_url()

    # 拼接URL
    if not url.startswith("http"):
        full_url = f"{base_url.rstrip('/')}/{url.lstrip('/')}"
    else:
        full_url = url

    # 构建认证头 - cookies优先
    if not cookies:
        cookies = os.getenv(f"DATASTACK_{environment.upper()}_COOKIE")
        if not cookies:
            cookies = _load_cookie_from_file(environment)
    auth_headers = _build_auth_headers(environment, token, cookies)
    if headers:
        auth_headers.update(headers)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.delete(full_url, params=params, headers=auth_headers)
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        return f"HTTP错误 {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"请求失败: {str(e)}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HTTP MCP Server")
    parser.add_argument("--transport", "-t", default="stdio", choices=["stdio", "http", "sse"],
                        help="Transport mode (default: stdio)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP/SSE transport")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port for HTTP/SSE transport")

    args = parser.parse_args()

    if args.transport == "http":
        print(f"🚀 Starting HTTP MCP Server on {args.host}:{args.port}")
        http_mcp.run(transport="http", host=args.host, port=args.port)
    elif args.transport == "sse":
        print(f"🚀 Starting SSE MCP Server on {args.host}:{args.port}")
        http_mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        print("🚀 Starting MCP Server (stdio mode)")
        http_mcp.run()
