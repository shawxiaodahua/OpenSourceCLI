"""JSON-RPC 2.0 协议实现 (stdio)。

CLI 进程通过子进程 stdin/stdout 与 Python 引擎通信：
- 每条消息为一行 JSON（以换行分隔）。
- 普通方法返回单行 JSON-RPC 响应。
- 流式方法（如 chat.send）返回多行事件，每行一个事件对象。
- 通知（无 id）不需要响应。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
import uuid
from typing import Any, AsyncGenerator, Awaitable, Callable, Union


JSONRPC_VERSION = "2.0"


class JsonRpcError(Exception):
    """JSON-RPC 错误对象。"""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

    def to_dict(self) -> dict:
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


# 标准 JSON-RPC 错误码
PARSE_ERROR = JsonRpcError(-32700, "Parse error")
INVALID_REQUEST = JsonRpcError(-32600, "Invalid Request")
METHOD_NOT_FOUND = JsonRpcError(-32601, "Method not found")
INVALID_PARAMS = JsonRpcError(-32602, "Invalid params")
INTERNAL_ERROR = JsonRpcError(-32603, "Internal error")


def create_request(method: str, params: dict, request_id: int | None = None) -> dict:
    """创建 JSON-RPC 请求。"""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
        "params": params,
        "id": request_id if request_id is not None else uuid.uuid4().int & 0x7FFFFFFF,
    }


def create_response(request_id: Any, result: Any = None, error: JsonRpcError | None = None) -> dict:
    """创建 JSON-RPC 响应。"""
    resp: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": request_id}
    if error is not None:
        resp["error"] = error.to_dict()
    else:
        resp["result"] = result
    return resp


def create_notification(method: str, params: dict) -> dict:
    """创建 JSON-RPC 通知（无 id，无需响应）。"""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
        "params": params,
    }


class StreamEvent:
    """流式事件构造器 — 引擎 -> CLI 的增量输出。"""

    __slots__ = ("type", "data")

    def __init__(self, event_type: str, **kwargs):
        self.type = event_type
        self.data = kwargs

    def to_dict(self) -> dict:
        return {"type": self.type, **self.data}

    # --- 常用事件工厂 ---
    @classmethod
    def stream_start(cls):
        return cls("stream_start")

    @classmethod
    def stream_end(cls):
        return cls("stream_end")

    @classmethod
    def text(cls, content: str):
        return cls("text", content=content)

    @classmethod
    def thinking(cls, content: str):
        return cls("thinking", content=content)

    @classmethod
    def tool_use(cls, name: str, input: dict, id: str):
        return cls("tool_use", name=name, input=input, id=id)

    @classmethod
    def tool_result(cls, id: str, content: Any, is_error: bool = False):
        return cls("tool_result", id=id, content=content, is_error=is_error)

    @classmethod
    def error(cls, message: str):
        return cls("error", message=message)


# 处理器返回类型：普通值（→ JSON 响应）或 async generator（→ 流式多行）
HandlerResult = Union[Any, AsyncGenerator[bytes, None]]


class JsonRpcServer:
    """JSON-RPC 服务端 — 从 stdin 读取请求，写入 stdout 响应/事件。"""

    def __init__(self, engine):
        self.engine = engine
        self._methods: dict[str, Callable[..., Awaitable[HandlerResult]]] = {
            "chat.send": self._handle_chat_send,
            "engine.status": self._handle_engine_status,
            "skill.list": self._handle_skill_list,
            "skill.load": self._handle_skill_load,
            "session.list": self._handle_session_list,
            "session.load": self._handle_session_load,
            "session.create": self._handle_session_create,
            "shutdown": self._handle_shutdown,
        }

    async def handle(self, raw: bytes) -> bytes | AsyncGenerator[bytes, None] | None:
        """处理单行 JSON-RPC 消息。

        返回：
        - None：通知，无需响应
        - bytes：单行 JSON-RPC 响应
        - AsyncGenerator[bytes]：流式响应，逐行事件
        """
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            return (json.dumps(create_response(None, error=PARSE_ERROR)) + "\n").encode()

        if not isinstance(message, dict) or message.get("jsonrpc") != JSONRPC_VERSION:
            return (json.dumps(create_response(None, error=INVALID_REQUEST)) + "\n").encode()

        method = message.get("method", "")
        params = message.get("params") or {}
        request_id = message.get("id")
        is_notification = request_id is None

        handler = self._methods.get(method)
        if handler is None:
            if is_notification:
                return None
            return (json.dumps(create_response(request_id, error=METHOD_NOT_FOUND)) + "\n").encode()

        try:
            # 流式方法（async generator function）直接调用，返回 generator
            if inspect.isasyncgenfunction(handler):
                if is_notification:
                    # 通知形式调用流式方法：消费但不回响应
                    async for _ in handler(params, request_id):
                        pass
                    return None
                return handler(params, request_id)

            # 普通异步方法
            result = await handler(params)
            if is_notification:
                return None
            return (json.dumps(create_response(request_id, result)) + "\n").encode()
        except JsonRpcError as e:
            return (json.dumps(create_response(request_id, error=e)) + "\n").encode()
        except Exception as e:  # noqa: BLE001
            err = JsonRpcError(-32603, f"Internal error: {e}")
            return (json.dumps(create_response(request_id, error=err)) + "\n").encode()

    # --- 方法处理器 ---

    async def _handle_chat_send(self, params: dict, request_id=None) -> AsyncGenerator[bytes, None]:
        """处理聊天请求 — 委托给 engine.chat()，逐行输出事件。

        每个事件被打上 streamId（= 请求 id），便于 CLI 在共享 stdout 上做多路解复用。
        """
        message = params.get("message", "")
        session_id = params.get("conversation_id") or params.get("session_id")

        async for event in self.engine.chat(message, session_id):
            # event 可能是 dict 或 StreamEvent 对象
            data = event if isinstance(event, dict) else event.to_dict()
            data["streamId"] = request_id
            yield (json.dumps(data) + "\n").encode()

    async def _handle_engine_status(self, params: dict) -> dict:
        provider_name = "unknown"
        if self.engine and getattr(self.engine, "provider", None):
            provider_name = self.engine.provider.model_name
        return {
            "status": "running",
            "provider": provider_name,
            "session_active": self.engine.session is not None if self.engine else False,
        }

    async def _handle_skill_list(self, params: dict) -> list:
        if self.engine and getattr(self.engine, "skills", None):
            return [s.to_summary() for s in self.engine.skills.list_skills()]
        return []

    async def _handle_skill_load(self, params: dict) -> dict:
        if not self.engine or not getattr(self.engine, "skills", None):
            raise METHOD_NOT_FOUND
        skill = self.engine.skills.load_skill(params.get("name", ""))
        if skill is None:
            raise JsonRpcError(-1, f"Skill not found: {params.get('name')}")
        self.engine.activate_skill(skill)
        return {"loaded": skill.name}

    async def _handle_session_list(self, params: dict) -> list:
        if self.engine:
            return self.engine.session_manager.list_sessions()
        return []

    async def _handle_session_load(self, params: dict) -> dict:
        if self.engine:
            self.engine.load_session(params.get("session_id", ""))
            return {"loaded": params.get("session_id")}
        return {}

    async def _handle_session_create(self, params: dict) -> dict:
        if self.engine:
            self.engine.new_session()
            return {"created": True}
        return {}

    async def _handle_shutdown(self, params: dict) -> None:
        if self.engine:
            await self.engine.shutdown()
        # 通过单独的机制退出；这里仅做清理
        return None

    # --- 主循环 ---

    async def serve(self) -> None:
        """主循环：从 stdin 读取消息，写响应到 stdout。"""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        writer = sys.stdout.buffer
        shutdown_event = asyncio.Event()

        while not shutdown_event.is_set():
            try:
                line = await reader.readline()
                if not line:
                    break  # EOF

                line = line.strip()
                if not line:
                    continue

                result = await self.handle(line)
                if result is None:
                    # 通知；若为 shutdown 则退出
                    try:
                        msg = json.loads(line)
                        if msg.get("method") == "shutdown":
                            shutdown_event.set()
                    except json.JSONDecodeError:
                        pass
                    continue

                if inspect.isasyncgen(result):
                    async for chunk in result:
                        writer.write(chunk)
                        writer.flush()
                else:
                    writer.write(result)
                    writer.flush()
            except (EOFError, BrokenPipeError):
                break
            except Exception:  # noqa: BLE001
                # 单条消息异常不应崩溃整个服务
                continue

        # 收到 shutdown 或 EOF，确保会话保存
        if self.engine:
            try:
                await self.engine.shutdown()
            except Exception:  # noqa: BLE001
                pass
