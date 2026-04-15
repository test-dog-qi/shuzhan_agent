"""测试记忆模块"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from shuzhan_agent.memory import MemoryTool, MemoryConfig
from shuzhan_agent.memory.storage import SQLiteDocumentStore
from shuzhan_agent.memory.vector_store import QDRANT_AVAILABLE


def test_memory_tool():
    """测试记忆工具"""
    print("=" * 60)
    print("记忆模块测试")
    print("=" * 60)
    load_dotenv()

    # 读取Qdrant配置
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    qdrant_collection = os.getenv("QDRANT_COLLECTION", "shuzhan_agent_test_vectors")

    print(f"\n[配置] Qdrant URL: {qdrant_url or '未设置'}")
    print(f"[配置] Qdrant API Key: {'已设置' if qdrant_api_key else '未设置'}")
    print(f"[配置] Qdrant Collection: {qdrant_collection}")

    # 检查Qdrant连接
    if not qdrant_url or not qdrant_api_key:
        print("\n⚠️ 警告: QDRANT_URL 或 QDRANT_API_KEY 未设置")
        print("   情景记忆将仅使用SQLite存储，向量检索将被跳过")
        use_qdrant = False
    else:
        use_qdrant = True
        print("\n✅ Qdrant配置完整，将进行完整测试")

    # 创建配置
    config = MemoryConfig(
        storage_path="./memory_data_test",
        working_memory_capacity=10,
        working_memory_ttl_minutes=60,
        qdrant_url=qdrant_url or "",
        qdrant_api_key=qdrant_api_key or "",
        qdrant_collection=qdrant_collection,
        qdrant_vector_size=384
    )

    # 创建MemoryTool
    print("\n[1] 创建MemoryTool...")
    memory = MemoryTool(user_id="test_user", config=config)
    print(f"    记忆管理器: {memory.memory_manager}")
    print(f"    启用的记忆类型: {list(memory.memory_manager.memory_types.keys())}")

    # 测试添加工作记忆
    print("\n[2] 测试添加工作记忆 (add)...")
    result = memory.execute("add", content="这是我的第一条工作记忆", memory_type="working", importance=0.8)
    print(f"    结果: {result}")

    result = memory.execute("add", content="第二条重要记忆 - 关于项目X", memory_type="working", importance=0.9)
    print(f"    结果: {result}")

    result = memory.execute("add", content="今天的会议讨论了项目计划", memory_type="working", importance=0.6)
    print(f"    结果: {result}")

    # 测试添加情景记忆
    print("\n[3] 测试添加情景记忆 (add, memory_type=episodic)...")
    result = memory.execute("add",
                            content="昨天与产品经理讨论了需求，她说优先级调整为P0",
                            memory_type="episodic",
                            importance=0.8,
                            outcome="确定需求优先级")
    print(f"    结果: {result}")

    result = memory.execute("add",
                            content="上次修复了一个严重bug，问题是数据库连接泄漏",
                            memory_type="episodic",
                            importance=0.7)
    print(f"    结果: {result}")

    # 测试搜索
    print("\n[4] 测试搜索 (search)...")
    result = memory.execute("search", query="项目", limit=3)
    print(f"    查询'项目':\n{result}")

    result = memory.execute("search", query="bug", limit=3)
    print(f"    查询'bug':\n{result}")

    # 测试统计
    print("\n[5] 测试统计 (stats)...")
    result = memory.execute("stats")
    print(f"    结果:\n{result}")

    # 测试摘要
    print("\n[6] 测试摘要 (summary)...")
    result = memory.execute("summary", limit=5)
    print(f"    结果:\n{result}")

    # 测试更新
    print("\n[7] 测试更新 (update)...")
    # 先搜索获取一个memory_id
    search_result = memory.execute("search", query="第一条", limit=1)
    print(f"    搜索结果: {search_result}")

    # 测试遗忘
    print("\n[8] 测试遗忘 (forget)...")
    result = memory.execute("forget", strategy="importance_based", threshold=0.9)
    print(f"    结果: {result}")

    # 测试整合
    print("\n[9] 测试整合 (consolidate)... (working -> episodic)")
    result = memory.execute("consolidate", from_type="working", to_type="episodic", importance_threshold=0.5)
    print(f"    结果: {result}")

    # 测试清空
    print("\n[10] 测试清空 (clear_all)...")
    result = memory.execute("clear_all")
    print(f"    结果: {result}")

    # 测试清理后统计
    print("\n[11] 清理后统计...")
    result = memory.execute("stats")
    print(f"    结果:\n{result}")

    print("\n" + "=" * 60)
    print("记忆模块测试完成!")
    print("=" * 60)

    return memory


def test_sqlite_only():
    """仅测试SQLite存储"""
    print("\n" + "=" * 60)
    print("SQLite存储单独测试")
    print("=" * 60)

    store = SQLiteDocumentStore(db_path="./memory_data_test/sqlite_only.db")

    # 添加记忆
    import time
    store.add_memory(
        memory_id="test_001",
        user_id="user1",
        content="测试记忆内容",
        memory_type="episodic",
        timestamp=int(time.time()),
        importance=0.8,
        properties={"tag": "test"}
    )

    # 搜索
    results = store.search_memories(user_id="user1", memory_type="episodic")
    print(f"搜索结果: {results}")

    # 统计
    stats = store.get_database_stats()
    print(f"数据库统计: {stats}")

    print("\nSQLite测试完成!")


def main():
    """主测试函数"""
    # 清理旧的测试数据
    import shutil
    test_db_path = "./memory_data_test"
    if os.path.exists(test_db_path):
        shutil.rmtree(test_db_path)
    os.makedirs(test_db_path, exist_ok=True)

    # 测试SQLite
    test_sqlite_only()

    # 测试完整记忆模块
    test_memory_tool()


if __name__ == "__main__":
    main()
