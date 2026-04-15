"""MiniMax LLM 客户端"""

import os
from typing import Any, Dict, List, Optional
import anthropic
from dotenv import load_dotenv


class MiniMaxLLMClient:
    """
    MiniMax LLM 客户端

    使用 Anthropic SDK 连接到 MiniMax API
    """
    load_dotenv()

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = None,
        max_tokens: int = 8192,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
        self.model = os.getenv("ANTHROPIC_MODEL")
        self.max_tokens = max_tokens

        # 使用环境变量配置base_url
        os.environ["ANTHROPIC_BASE_URL"] = self.base_url

        self._client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送聊天请求

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            tools: 工具定义列表
            system_prompt: 独立的系统提示（会覆盖 messages 中的 system 消息）

        Returns:
            响应内容
        """
        # 转换消息格式
        anthropic_messages = []
        system_content = system_prompt

        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                if system_content is None:
                    system_content = msg.get("content", "")
                continue
            anthropic_messages.append({
                "role": role,
                "content": msg.get("content", "")
            })

        # 构建请求参数
        request_kwargs = {
            "model": self.model or "claude-3-5-sonnet-20241022",
            "max_tokens": self.max_tokens,
            "messages": anthropic_messages,
        }

        # 添加系统提示
        if system_content:
            request_kwargs["system"] = system_content

        if tools:
            request_kwargs["tools"] = tools

        # 添加额外参数（如 tool_choice）
        if kwargs:
            request_kwargs.update(kwargs)

        # 发送请求
        response = self._client.messages.create(**request_kwargs)

        # 解析响应
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "id": block.id,
                    "arguments": block.input
                })

        return {
            "content": content,
            "tool_calls": tool_calls if tool_calls else [],
        }


class LLMMixin:
    """
    LLM混合类

    提供LLM调用能力
    """

    def __init__(self, llm_client: Optional[MiniMaxLLMClient] = None):
        self._llm = llm_client

    def set_llm(self, llm_client: MiniMaxLLMClient) -> None:
        """设置LLM客户端"""
        self._llm = llm_client

    async def think(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        使用LLM思考

        Args:
            prompt: 输入提示
            tools: 工具定义

        Returns:
            LLM响应
        """
        if not self._llm:
            raise ValueError("LLM client not set")

        messages = [{"role": "user", "content": prompt}]
        return await self._llm.chat(messages=messages, tools=tools)
