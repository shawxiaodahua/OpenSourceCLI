"""Tests for shaw.protocol"""

import json

import pytest

from shaw.protocol import (
    JsonRpcServer,
    JsonRpcError,
    create_request,
    create_response,
    create_notification,
    StreamEvent,
    PARSE_ERROR,
    METHOD_NOT_FOUND,
)


def test_create_request():
    """创建 JSON-RPC 请求"""
    request = create_request("chat.send", {"message": "hello"})
    assert request["jsonrpc"] == "2.0"
    assert request["method"] == "chat.send"
    assert request["params"]["message"] == "hello"
    assert "id" in request


def test_create_request_with_id():
    """指定 ID"""
    request = create_request("chat.send", {}, request_id=42)
    assert request["id"] == 42


def test_create_response_success():
    """成功响应"""
    resp = create_response(1, result={"ok": True})
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"] == {"ok": True}
    assert "error" not in resp


def test_create_response_error():
    """错误响应"""
    resp = create_response(1, error=METHOD_NOT_FOUND)
    assert resp["error"]["code"] == -32601
    assert resp["error"]["message"] == "Method not found"


def test_create_notification():
    """通知无 id"""
    notif = create_notification("shutdown", {})
    assert notif["jsonrpc"] == "2.0"
    assert notif["method"] == "shutdown"
    assert "id" not in notif


def test_json_rpc_error_to_dict():
    """错误对象序列化"""
    error = JsonRpcError(code=-32601, message="Method not found", data={"hint": "x"})
    d = error.to_dict()
    assert d["code"] == -32601
    assert d["message"] == "Method not found"
    assert d["data"] == {"hint": "x"}


def test_stream_event_text():
    """StreamEvent 构造器"""
    ev = StreamEvent.text("hello")
    assert ev.to_dict() == {"type": "text", "content": "hello"}

    ev = StreamEvent.tool_use("Read", {"path": "/a"}, "t1")
    assert ev.to_dict() == {"type": "tool_use", "name": "Read", "input": {"path": "/a"}, "id": "t1"}


async def test_server_unknown_method():
    """未知方法返回 -32601"""
    server = JsonRpcServer(engine=None)
    response = await server.handle(b'{"jsonrpc":"2.0","id":1,"method":"unknown","params":{}}')
    result = json.loads(response)
    assert result["error"]["code"] == -32601


async def test_server_malformed_json():
    """畸形 JSON 返回 -32700"""
    server = JsonRpcServer(engine=None)
    response = await server.handle(b"not json")
    result = json.loads(response)
    assert result["error"]["code"] == -32700


async def test_server_notification_no_response():
    """通知（无 id）返回 None"""
    server = JsonRpcServer(engine=None)
    response = await server.handle(b'{"jsonrpc":"2.0","method":"shutdown","params":{}}')
    assert response is None


async def test_server_streaming_method():
    """流式方法返回 async generator（逐行事件）"""
    events = [
        {"type": "text", "content": "hi"},
        {"type": "stream_end"},
    ]

    class FakeEngine:
        async def chat(self, message, session_id=None):
            for ev in events:
                yield ev

    server = JsonRpcServer(engine=FakeEngine())
    raw = b'{"jsonrpc":"2.0","id":5,"method":"chat.send","params":{"message":"hi"}}'
    result = await server.handle(raw)

    # 流式方法返回 async generator
    import inspect

    assert inspect.isasyncgen(result)

    lines = []
    async for chunk in result:
        lines.append(json.loads(chunk.decode().strip()))

    assert lines[0]["type"] == "text"
    assert lines[0]["content"] == "hi"
    assert lines[-1]["type"] == "stream_end"


async def test_server_engine_status():
    """engine.status 返回普通响应"""
    class FakeEngine:
        provider = type("P", (), {"model_name": "claude-test"})()
        session = None

    server = JsonRpcServer(engine=FakeEngine())
    raw = b'{"jsonrpc":"2.0","id":1,"method":"engine.status","params":{}}'
    response = await server.handle(raw)
    result = json.loads(response)
    assert result["result"]["status"] == "running"
    assert result["result"]["provider"] == "claude-test"
