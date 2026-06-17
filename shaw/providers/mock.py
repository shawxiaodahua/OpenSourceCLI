"""Mock Provider — 离线/测试用，无需 API Key。

走完一次完整的工具调用循环，便于端到端验证 CLI 与引擎链路：
- 收到用户消息 → 请求 Bash 工具执行 `echo <msg>`
- 收到工具结果 → 产出最终文本回复
"""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

from shaw.provider import BaseProvider, Message, StreamEvent, ToolDef


class MockProvider(BaseProvider):
    """确定性 mock 提供商，模拟 LLM 的工具调用循环。"""

    def __init__(self, model: str = "mock-0.1"):
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    async def send(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        if not messages:
            yield StreamEvent(type="text", content="(empty)")
            yield StreamEvent(type="done")
            return

        last = messages[-1]
        content = last.content

        # 上一条是工具结果 → 收尾回复
        if last.role == "user" and isinstance(content, list):
            tool_text = ""
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_text = str(block.get("content", ""))
            yield StreamEvent(type="text", content=f"Mock 回复：我执行了工具，得到：{tool_text}")
            yield StreamEvent(type="done")
            return

        # 否则请求一次 Bash 工具调用
        user_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        yield StreamEvent(type="text", content="（mock）我先调用一个工具试试。")
        yield StreamEvent(
            type="tool_use",
            tool_name="Bash",
            tool_input={"command": f"echo mock:{user_text[:40]}"},
            tool_use_id=f"mock_{uuid.uuid4().hex[:8]}",
        )
        yield StreamEvent(type="done")
