#!/usr/bin/env python3
"""实际执行：创建数栈项目"""

import asyncio
import os
import sys
import httpx
from datetime import datetime

# 添加src/shuzhan_agent到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'shuzhan_agent'))

from dotenv import load_dotenv


async def create_project(project_name: str = "test_030_1"):
    """创建数栈项目"""
    load_dotenv()

    print("=" * 60)
    print("数栈智能体工程师 - 创建项目")
    print("=" * 60)

    # 配置
    base_url = os.getenv("DATASTACK_BASE_URL")
    username = os.getenv("DATASTACK_USERNAME")
    password = os.getenv("DATASTACK_PASSWORD")

    print(f"\n[配置]")
    print(f"  URL: {base_url}")
    print(f"  User: {username}")
    print(f"  项目名: {project_name}")

    # 1. 登录获取token
    print("\n[1/3] 登录认证...")

    async with httpx.AsyncClient(base_url=base_url, timeout=30, follow_redirects=True) as client:
        # 数栈登录流程较复杂，需要SM2加密
        # 1. 先获取公钥
        # 2. SM2加密密码
        # 3. 登录

        # 由于SM2加密较复杂，暂时跳过登录
        # 询问用户是否有现成的token

        print("  ⚠️ 数栈登录需要SM2加密，暂时跳过")
        print("  请提供以下信息之一:")
        print("  1. 已登录的Cookie字符串")
        print("  2. 直接可用的Token")
        print("  3. 或者告诉我如何获取验证码")

        # 尝试简单的登录请求看看是否需要验证码
        simple_login_data = {
            "username": username,
            "password": password,
        }
        login_resp = await client.post(
            "/uic/api/v2/account/login",
            data=simple_login_data  # 使用data而非json
        )
        print(f"\n  简单登录响应: {login_resp.status_code}")
        try:
            login_json = login_resp.json()
            print(f"  响应内容: {login_json}")
        except:
            print(f"  响应内容: {login_resp.text[:200]}")

        return {"success": False, "error": "需要实现SM2加密登录"}

        # 2. 创建项目
        print("\n[2/3] 创建项目...")
        timestamp = datetime.now().strftime("%m%d%H%M")

        project_params = {
            "projectName": project_name,
            "projectAlias": f"测试项目_{timestamp}",
            "projectOwnerId": "1",
            "scheduleStatus": 0,
            "isAllowDownload": 1,
        }

        headers = {"Authorization": f"Bearer {token}"} if token else {}
        print(f"  发送创建请求到 /api/rdos/common/project/createProject ...")

        create_resp = await client.post(
            "/api/rdos/common/project/createProject",
            json=project_params,
            headers=headers
        )
        print(f"  响应状态: {create_resp.status_code}")

        try:
            create_json = create_resp.json()
            print(f"  响应内容: {create_json}")
        except:
            print(f"  响应内容(非JSON): {create_resp.text[:500]}")
            create_json = {}

        create_code = create_json.get("code")
        create_msg = create_json.get("msg")

        if create_code == 0:
            project_id = create_json.get("data", {}).get("projectId")
            print(f"  ✓ 项目创建成功! ID: {project_id}")
            return {"success": True, "project_id": project_id, "data": create_json}
        else:
            print(f"  ✗ 创建失败: {create_msg}")
            return {"success": False, "error": create_msg}

    # 3. 验证结果
    print("\n[3/3] 验证项目...")
    # TODO: 调用查询接口验证项目是否创建成功


async def main():
    result = await create_project("test_030_1")
    print("\n" + "=" * 60)
    print("执行完成")
    print(f"结果: {result}")
    print("=" * 60)
    return result


if __name__ == "__main__":
    asyncio.run(main())
