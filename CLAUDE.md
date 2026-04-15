# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shuzhan Agent (数栈智能体工程师) is an LLM-driven agent for automating tasks on the Datastack offline platform. It understands natural language instructions, autonomously decides which tools to use, and executes tasks like test data construction.

## Commands

```bash
# Install dependencies (using uv)
uv pip install -e .

# Run specific test script (root-level test_*.py files are standalone scripts)
uv run python test_<name>.py
```

## Architecture

### Core Agent (`src/shuzhan_agent/agent/llm_driven_agent.py`)

`LLMDrivenAgent` is the central component with Plan-and-Solve + Reflection architecture:
1. **Planner** - Task decomposition (generates multi-step plan), embedded as inner class
2. **Executor** - Step-by-step execution with tool calling
3. **Reflector** - Result verification, triggers retry/replan on failure
4. **Context Engine** - GSSC pipeline for context optimization
5. **Memory Manager** - Working + Episodic memory integration

Agent Loop: `Planner → Executor → Reflector → (retry/replan if needed) → Memory`

**Tool Priority Chain**: MCP Tool Proxy → MCP Wrapper → Built-in tools (LoginTool, http_request, memory_*, browser_*)

### Reflector (`src/shuzhan_agent/agent/reflector.py`)

Reflection pattern for self-correction:
- Validates step execution results
- Quick-check for error patterns (timeout, network, auth errors)
- Deep-reflect using LLM analysis
- Decides: retry (temporary errors) vs replan (strategy errors)

Supports MCP tool wrapper for dynamic tool loading:
```python
agent = LLMDrivenAgent(
    llm_client=llm_client,
    mcp_wrapper=mcp_wrapper,  # Optional MCP integration
    enable_planning=True,
    enable_context_engine=True
)
```

### Memory Module (`src/shuzhan_agent/memory/`)

| File | Purpose |
|------|---------|
| `working.py` | TTL-based working memory (session-scoped) |
| `episodic.py` | Long-term episodic memory (SQLite + Qdrant vector search) |
| `storage.py` | SQLite document store |
| `embedding.py` | Text embedding (text-embedding-v4 primary, sentence-transformers fallback) |
| `vector_store.py` | Qdrant vector database integration |
| `memory_tool.py` | Unified memory tool interface |
| `manager.py` | Memory manager coordinating all memory types |

### MCP Layer (`src/shuzhan_agent/mcp/`)

| File | Purpose |
|------|---------|
| `http_mcp.py` | FastMCP server with GET/POST/PUT/DELETE HTTP tools |
| `login_mcp.py` | FastMCP server with LoginTool |
| `playwright_integration.py` | Browser automation + VisionCaptchaSolver |

### Tools (`src/shuzhan_agent/tools/`)

| File | Purpose |
|------|---------|
| `mcp_wrapper.py` | MCPToolWrapper - connects to MCP servers |
| `mcp_wrapped_tool.py` | MCPWrappedTool - wraps single MCP tool |
| `base.py` | Tool/ToolParameter base classes |

### LLM Client (`src/shuzhan_agent/utils/llm_client.py`)

`MiniMaxLLMClient` - Uses Anthropic SDK to connect to MiniMax API

## Key Capabilities

1. **Planning**: Complex tasks are decomposed into steps via LLM
2. **Reflection**: Self-correction mechanism (retry/replan on failure)
3. **Memory**: Working memory (TTL) + Episodic memory (vector search)
4. **Context Engineering**: GSSC pipeline prevents context rot
5. **MCP Integration**: Dynamic tool loading via MCP protocol

## Environment Configuration

Configure via `.env` file:
- `ANTHROPIC_API_KEY` - MiniMax API key
- `ANTHROPIC_BASE_URL` - API endpoint (default: `https://api.minimaxi.com/anthropic`)
- `DATASTACK_USERNAME` / `DATASTACK_PASSWORD` - Platform credentials
- `QDRANT_URL` / `QDRANT_API_KEY` - Vector database (optional)
- `EMBED_API_KEY` - Embedding API key (text-embedding-v4)
