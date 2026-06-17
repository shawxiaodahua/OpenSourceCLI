"""Tests for shaw.session 与 shaw.engine — LLM 循环核心。"""

from typing import AsyncIterator

import pytest

from shaw.engine import Engine
from shaw.session import Session, SessionManager
from shaw.provider import BaseProvider, StreamEvent, Message, ToolDef
from shaw.tools.registry import ToolRegistry, BaseTool


# --- Session ---

def test_session_creation():
    s = Session(session_id="test-1")
    assert s.session_id == "test-1"
    assert len(s.messages) == 0


def test_session_add_message():
    s = Session(session_id="t")
    s.add_message(role="user", content="hello")
    assert len(s.messages) == 1
    assert s.messages[0]["role"] == "user"
    assert s.messages[0]["content"] == "hello"


def test_session_add_tool_use_and_result():
    s = Session(session_id="t")
    s.add_tool_use("Read", {"path": "/a"}, "tool1")
    s.add_tool_result("tool1", "file content")
    # assistant tool_use + user tool_result
    assert len(s.messages) == 2
    assert s.messages[0]["role"] == "assistant"
    assert s.messages[0]["content"][0]["type"] == "tool_use"
    assert s.messages[1]["role"] == "user"
    assert s.messages[1]["content"][0]["type"] == "tool_result"


def test_session_serialize_roundtrip():
    s = Session(session_id="t")
    s.add_message("user", "hi")
    data = s.to_dict()
    s2 = Session.from_dict(data)
    assert s2.session_id == "t"
    assert len(s2.messages) == 1


def test_session_manager_save_load(tmp_path):
    mgr = SessionManager(storage_dir=tmp_path)
    s = Session(session_id="abc")
    s.add_message("user", "hi")
    mgr.save(s)

    loaded = mgr.load("abc")
    assert loaded is not None
    assert loaded.session_id == "abc"
    assert len(loaded.messages) == 1

    sessions = mgr.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "abc"


# --- Engine with MockProvider ---

class MockProvider(BaseProvider):
    """按调用顺序返回预设事件序列的 mock provider。"""

    def __init__(self, responses: list[list[StreamEvent]]):
        self._responses = responses
        self._call_count = 0

    @property
    def model_name(self) -> str:
        return "mock-model"

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    async def send(self, system, messages, tools=None) -> AsyncIterator[StreamEvent]:
        if self._call_count < len(self._responses):
            for event in self._responses[self._call_count]:
                yield event
            self._call_count += 1


class EchoTool(BaseTool):
    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(name="Echo", description="Echo input", params=[])

    def execute(self, **kwargs) -> str:
        return "echo: " + str(kwargs)


def _engine_with(provider, registry=None):
    registry = registry or ToolRegistry()
    return Engine(provider=provider, tools=registry, harness=None, config={})


async def test_engine_simple_chat(tmp_path):
    """纯文本对话，无工具调用"""
    provider = MockProvider([
        [StreamEvent(type="text", content="Hello!"), StreamEvent(type="done")],
    ])
    engine = _engine_with(provider)
    engine.session_manager = SessionManager(storage_dir=tmp_path)

    events = [e async for e in engine.chat("Hi", "s1")]
    assert any(e["type"] == "text" and e["content"] == "Hello!" for e in events)
    assert events[-1]["type"] == "stream_end"


async def test_engine_tool_use_loop(tmp_path):
    """工具调用循环：LLM 调用工具 → 结果反馈 → 继续"""
    provider = MockProvider([
        [
            StreamEvent(type="text", content="Let me check..."),
            StreamEvent(type="tool_use", tool_name="Echo", tool_input={"key": "value"}, tool_use_id="tool1"),
            StreamEvent(type="done"),
        ],
        [
            StreamEvent(type="text", content="Done!"),
            StreamEvent(type="done"),
        ],
    ])
    registry = ToolRegistry()
    registry.register(EchoTool())
    engine = _engine_with(provider, registry)
    engine.session_manager = SessionManager(storage_dir=tmp_path)

    events = [e async for e in engine.chat("Check this", "s2")]

    text_events = [e for e in events if e["type"] == "text"]
    tool_use_events = [e for e in events if e["type"] == "tool_use"]
    tool_result_events = [e for e in events if e["type"] == "tool_result"]

    assert any("Done!" in e["content"] for e in text_events)
    assert len(tool_use_events) == 1
    assert tool_use_events[0]["name"] == "Echo"
    assert len(tool_result_events) == 1
    assert "echo" in tool_result_events[0]["content"]


async def test_engine_max_iterations(tmp_path):
    """LLM 持续请求工具调用应受最大迭代次数限制"""
    # 每轮都请求工具调用，永不停止
    loop_response = [StreamEvent(type="tool_use", tool_name="Echo", tool_input={}, tool_use_id="x"), StreamEvent(type="done")]
    provider = MockProvider([loop_response] * 100)
    registry = ToolRegistry()
    registry.register(EchoTool())
    engine = _engine_with(provider, registry)
    engine.session_manager = SessionManager(storage_dir=tmp_path)

    events = [e async for e in engine.chat("loop", "s3")]
    # 应在到达上限后停止，不会无限循环
    tool_uses = [e for e in events if e["type"] == "tool_use"]
    assert len(tool_uses) <= 25  # 默认上限


async def test_engine_session_persisted(tmp_path):
    """auto_save 时会话被持久化"""
    provider = MockProvider([
        [StreamEvent(type="text", content="ok"), StreamEvent(type="done")],
    ])
    engine = _engine_with(provider)
    engine.session_manager = SessionManager(storage_dir=tmp_path)

    async for _ in engine.chat("Hi", "persist-me"):
        pass

    assert (tmp_path / "persist-me.json").exists()
