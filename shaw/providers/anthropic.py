"""Anthropic Claude Provider 实现 — 支持 streaming + tool use。

使用官方 anthropic SDK 的 messages.stream() 上下文管理器，
逐事件解析为统一的 StreamEvent。
"""

from __future__ import annotations

import json
import math
import threading
from typing import Any, AsyncIterator

from shaw.provider import BaseProvider, Message, StreamEvent, ToolDef


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API 提供商。"""

    # max_tokens 绝对上限（sanity check）。
    # 这是各家用模型输出上限的宽松上界（claude-sonnet-4 为 64000，glm-4.6 为
    # 16384，火山 Ark 兼容层另有服务端限制）。Shaw 不按模型细分 clamp（模型表
    # 易过时），仅用一个安全上界拦截误填的天文数字，防止 API 直接 400。
    # 真实模型限制仍由端点决定，设到该值附近若报错需下调。
    MAX_TOKENS_LIMIT = 128000

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
        # 工具 schema 缓存：tools 列表在多轮循环中不变，避免每轮重复构建。
        self._tools_cache_src: list[ToolDef] | None = None
        self._tools_cache: list[dict] | None = None
        # 后台预热状态：preload() 在独立线程完成 import + 构造 AsyncAnthropic，
        # 把数秒耗时重叠到用户打字时间；_client_ready 用于主线程同步等待。
        self._preloaded = False
        self._preload_lock = threading.Lock()
        self._client_ready = threading.Event()
        self._client_ready.set()  # 默认就绪；preload 启动后由后台线程置位

    @property
    def model_name(self) -> str:
        return self._model

    def count_tokens(self, text: str) -> int:
        """粗略估算 token 数（英文约 3.5 字符/token，中文更密）。"""
        if not text:
            return 0
        return math.ceil(len(text) / 3.5)

    def preload(self) -> None:
        """在后台线程预热 anthropic SDK 导入 + 客户端构造。

        anthropic SDK 在 WSL2/慢盘下首次导入与客户端构造可达数秒。若推迟到首
        次 send() 才做，会整段阻塞事件循环——用户首条消息要卡到完成才出字。
        这里在引擎启动后立即用 daemon 线程并行完成 import + `AsyncAnthropic()`
        构造，把这段耗时重叠到用户思考/打字的时间。线程安全：客户端构造不发
        起网络请求，仅本地资源初始化；属性读写受 GIL 保护，用 Event 做同步。
        """
        with self._preload_lock:
            if self._preloaded or self._client is not None:
                return
            self._preloaded = True
            self._client_ready.clear()

        def _warm() -> None:
            try:
                self._client = self._build_client()
            except Exception:  # noqa: BLE001
                # 构造失败留给 _get_client 按原逻辑重试/抛出，这里静默
                pass
            finally:
                self._client_ready.set()

        threading.Thread(
            target=_warm, name="shaw-anthropic-preload", daemon=True
        ).start()

    def _build_client(self):
        """构造并返回 AsyncAnthropic 客户端（可被 preload 后台调用）。"""
        from anthropic import AsyncAnthropic

        kwargs: dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return AsyncAnthropic(**kwargs)

    def _get_client(self):
        """返回 AsyncAnthropic 客户端：优先用后台预热结果，否则就地构造。"""
        if self._client is None:
            # 后台预热进行中则等其完成（重叠掉数秒导入/构造耗时）
            if self._preloaded and not self._client_ready.is_set():
                self._client_ready.wait()
            # 预热未启动或失败：就地构造（保留原行为）
            if self._client is None:
                self._client = self._build_client()
        return self._client

    def _to_anthropic_tools(self, tools: list[ToolDef]) -> list[dict]:
        """将内部 ToolDef 转换为 Anthropic API 的 tools 格式。

        同一 tools 列表对象在多轮循环中复用，命中缓存直接返回，避免每轮重建。
        """
        if tools is self._tools_cache_src and self._tools_cache is not None:
            return self._tools_cache

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
        self._tools_cache_src = tools
        self._tools_cache = result
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

        # clamp 到绝对上限，防止误填超大值导致 API 400
        max_tokens = self._max_tokens
        if max_tokens > self.MAX_TOKENS_LIMIT:
            import sys

            sys.stderr.write(
                f"[shaw] max_tokens={max_tokens} 超过上限 {self.MAX_TOKENS_LIMIT}，"
                f"已自动限制。各模型真实输出上限通常更低（claude-sonnet-4: 64000，"
                f"glm-4.6: 16384），按需下调。\n"
            )
            max_tokens = self.MAX_TOKENS_LIMIT

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
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
