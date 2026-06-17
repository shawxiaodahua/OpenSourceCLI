"""Tests for shaw.provider 与 AnthropicProvider 流式解析。"""

from dataclasses import dataclass
from typing import AsyncIterator

import pytest

from shaw.provider import BaseProvider, Message, ToolDef, ToolParam, StreamEvent
from shaw.providers.anthropic import AnthropicProvider


def test_message_creation():
    msg = Message(role="user", content="hello")
    assert msg.role == "user"
    assert msg.content == "hello"


def test_tool_def():
    param = ToolParam(name="path", type="string", description="File path", required=True)
    tool = ToolDef(name="Read", description="Read a file", params=[param])
    assert tool.name == "Read"
    assert tool.params[0].name == "path"
    assert tool.params[0].required is True


def test_base_provider_cannot_instantiate():
    with pytest.raises(TypeError):
        BaseProvider()  # type: ignore[abstract]


def test_anthropic_provider_init():
    provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-6-20250515")
    assert provider.model_name == "claude-sonnet-4-6-20250515"


def test_anthropic_count_tokens():
    provider = AnthropicProvider(api_key="k", model="m")
    # 估算应返回正整数
    assert provider.count_tokens("hello world") > 0
    assert provider.count_tokens("") == 0


def test_anthropic_to_anthropic_tools():
    provider = AnthropicProvider(api_key="k", model="m")
    tool = ToolDef(
        name="Read",
        description="Read file",
        params=[
            ToolParam(name="path", type="string", description="p", required=True),
            ToolParam(name="offset", type="integer", description="o", required=False),
        ],
    )
    result = provider._to_anthropic_tools([tool])
    assert result[0]["name"] == "Read"
    assert result[0]["input_schema"]["required"] == ["path"]
    assert result[0]["input_schema"]["properties"]["path"]["type"] == "string"


# --- 流式解析测试：用 fake client 模拟 Anthropic SDK 事件流 ---

@dataclass
class FakeDelta:
    type: str
    text: str = ""
    partial_json: str = ""


@dataclass
class FakeContentBlock:
    type: str  # "text" | "tool_use"
    name: str = ""
    id: str = ""


@dataclass
class FakeEvent:
    type: str
    content_block: FakeContentBlock | None = None
    delta: FakeDelta | None = None


class FakeStream:
    """模拟 anthropic SDK 的 messages.stream() 上下文管理器 + 异步迭代。"""

    def __init__(self, events):
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for e in self._events:
            yield e


class FakeMessages:
    def __init__(self, events):
        self._events = events

    def stream(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeStream(self._events)


class FakeClient:
    def __init__(self, events):
        self.messages = FakeMessages(events)


async def test_anthropic_stream_text_and_tool_use():
    """解析纯文本 + 工具调用事件流"""
    events = [
        FakeEvent("content_block_start", content_block=FakeContentBlock("text")),
        FakeEvent("content_block_delta", delta=FakeDelta("text_delta", text="Hello ")),
        FakeEvent("content_block_delta", delta=FakeDelta("text_delta", text="world")),
        FakeEvent("content_block_stop"),
        FakeEvent("content_block_start", content_block=FakeContentBlock("tool_use", name="Read", id="t1")),
        FakeEvent("content_block_delta", delta=FakeDelta("input_json_delta", partial_json='{"path":')),
        FakeEvent("content_block_delta", delta=FakeDelta("input_json_delta", partial_json='"/a/b"}')),
        FakeEvent("content_block_stop"),
        FakeEvent("message_stop"),
    ]

    provider = AnthropicProvider(api_key="k", model="m", client=FakeClient(events))
    out = []
    async for ev in provider.send(system="sys", messages=[Message("user", "hi")], tools=None):
        out.append(ev)

    texts = [e for e in out if e.type == "text"]
    tool_uses = [e for e in out if e.type == "tool_use"]
    dones = [e for e in out if e.type == "done"]

    assert "".join(t.content for t in texts) == "Hello world"
    assert len(tool_uses) == 1
    assert tool_uses[0].tool_name == "Read"
    assert tool_uses[0].tool_input == {"path": "/a/b"}
    assert tool_uses[0].tool_use_id == "t1"
    assert len(dones) == 1


async def test_anthropic_stream_empty_tool_input():
    """工具调用无 input_json_delta 时 input 为空 dict"""
    events = [
        FakeEvent("content_block_start", content_block=FakeContentBlock("tool_use", name="Bash", id="t2")),
        FakeEvent("content_block_stop"),
        FakeEvent("message_stop"),
    ]
    provider = AnthropicProvider(api_key="k", model="m", client=FakeClient(events))
    out = [e async for e in provider.send("s", [Message("user", "x")])]
    tu = [e for e in out if e.type == "tool_use"][0]
    assert tu.tool_input == {}
