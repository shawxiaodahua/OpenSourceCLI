"""Provider 抽象层 — LLM 提供商统一接口。

所有 provider 实现 BaseProvider，向上层（Engine）提供统一的流式接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class ToolParam:
    """工具参数定义。"""

    name: str
    type: str
    description: str
    required: bool = False


@dataclass
class ToolDef:
    """工具定义（用于 LLM 函数调用声明）。"""

    name: str
    description: str
    params: list[ToolParam] = field(default_factory=list)


@dataclass
class Message:
    """对话消息。role: user | assistant | system；content 可为 str 或结构化内容块列表。"""

    role: str
    content: Any  # str | list[dict]


@dataclass
class StreamEvent:
    """Provider 产出的流式事件。

    type 取值：
    - "text": 纯文本片段
    - "thinking": 扩展思考片段
    - "tool_use": 工具调用请求
    - "done": 本轮响应结束
    """

    type: str
    content: Any = None
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    tool_use_id: str = ""


class BaseProvider(ABC):
    """LLM 提供商抽象基类。"""

    @abstractmethod
    async def send(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """发送消息到 LLM 并流式返回事件。"""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """估算 token 数量。"""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """当前模型名称。"""
        ...
