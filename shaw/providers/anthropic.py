"""Anthropic Claude Provider 实现 — 支持 streaming + tool use。

使用官方 anthropic SDK 的 messages.stream() 上下文管理器，
逐事件解析为统一的 StreamEvent。
"""

from __future__ import annotations

import json
import math
from typing import Any, AsyncIterator

from shaw.provider import BaseProvider, Message, StreamEvent, ToolDef


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API 提供商。"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6-20250515",
        max_tokens: int = 8192,
        base_url: str | None = None,
        client: Any | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._base_url = base_url
        self._client = client  # 可注入，便于测试

    @property
    def model_name(self) -> str:
        return self._model

    def count_tokens(self, text: str) -> int:
        """粗略估算 token 数（英文约 3.5 字符/token，中文更密）。"""
        if not text:
            return 0
        return math.ceil(len(text) / 3.5)

    def _get_client(self):
        """延迟初始化 Anthropic 异步客户端。"""
        if self._client is None:
            from anthropic import AsyncAnthropic

            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = AsyncAnthropic(**kwargs)
        return self._client

    def _to_anthropic_tools(self, tools: list[ToolDef]) -> list[dict]:
        """将内部 ToolDef 转换为 Anthropic API 的 tools 格式。"""
        result = []
        for tool in tools:
            properties: dict[str, Any] = {}
            required: list[str] = []
            for param in tool.params:
                properties[param.name] = {
                    "type": param.type,
                    "description": param.description,
                }
                if param.required:
                    required.append(param.name)

            schema: dict[str, Any] = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required

            result.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": schema,
                }
            )
        return result

    def _to_anthropic_messages(self, messages: list[Message]) -> list[dict]:
        """将内部 Message 转换为 Anthropic messages 格式。

        content 若为 str 则直接使用；若为结构化块列表则原样传递
        （用于 tool_use / tool_result 多块消息）。
        """
        result = []
        for msg in messages:
            if msg.role == "system":
                continue  # system 通过顶层 system 参数传递
            result.append({"role": msg.role, "content": msg.content})
        return result

    async def send(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """发送消息到 Claude 并流式返回事件。"""
        client = self._get_client()

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": self._to_anthropic_messages(messages),
        }
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)

        async with client.messages.stream(**kwargs) as stream:
            current_tool_name = ""
            current_tool_id = ""
            current_tool_input = ""

            async for event in stream:
                etype = getattr(event, "type", "")

                if etype == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block is not None and getattr(block, "type", "") == "tool_use":
                        current_tool_name = block.name
                        current_tool_id = block.id
                        current_tool_input = ""

                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    dtype = getattr(delta, "type", "")
                    if dtype == "text_delta":
                        yield StreamEvent(type="text", content=delta.text)
                    elif dtype == "thinking_delta":
                        yield StreamEvent(type="thinking", content=getattr(delta, "thinking", ""))
                    elif dtype == "input_json_delta":
                        current_tool_input += getattr(delta, "partial_json", "")

                elif etype == "content_block_stop":
                    if current_tool_name:
                        try:
                            tool_input = json.loads(current_tool_input) if current_tool_input else {}
                        except json.JSONDecodeError:
                            tool_input = {}
                        yield StreamEvent(
                            type="tool_use",
                            tool_name=current_tool_name,
                            tool_input=tool_input,
                            tool_use_id=current_tool_id,
                        )
                        current_tool_name = ""
                        current_tool_id = ""
                        current_tool_input = ""

                elif etype == "message_stop":
                    yield StreamEvent(type="done")
