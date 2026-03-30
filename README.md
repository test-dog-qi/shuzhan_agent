# Shuzhan Agent - 数栈智能体工程师

一个专注于数栈离线平台的智能体工程师，作为你的数字替身自主完成测试数据构造任务。

## 核心能力

- **意图理解**: 解析自然语言指令
- **任务分解**: 将需求分解为可执行步骤
- **自主执行**: 调用MCP/Skills完成任务
- **问题诊断**: 识别并尝试修复问题
- **多种输出**: 报告/实时进度/可交互

## 快速开始

```bash
# 安装依赖
pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入配置

# 运行
python -m shuzhan_agent.main
```

## 项目结构

```
shuzhan_agent/
├── agent/              # Agent核心
│   ├── base.py        # Agent基类
│   ├── datastack_agent.py  # 数栈专家Agent
│   └── mixins/        # Mixin模块
│       ├── offline_expert.py   # 离线专家
│       └── troubleshooter.py   # 问题排查
├── mcp/               # MCP Server
│   ├── base.py       # MCP基类
│   └── datastack_mcp.py  # 数栈MCP实现
├── skills/            # Skills
│   └── notification.py  # 通知技能
├── config/            # 配置
│   └── offline_flows.py  # 离线流程定义
└── main.py           # 入口
```

## 使用示例

```python
from shuzhan_agent.main import ShuzhanAgent

# 创建Agent
agent = ShuzhanAgent(llm=your_llm_client, environment={"version": "6.2"})

# 执行主流程回归测试
result = await agent.execute_main_flow(env_name="offline_62")
```
