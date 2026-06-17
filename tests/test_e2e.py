"""端到端测试 — 启动真实引擎子进程，通过 stdio JSON-RPC 交互。

使用 SHAW_MOCK=1 走 MockProvider，无需 API Key，验证完整链路：
协议帧 → 引擎 → 工具循环 → 流式事件回传。

读取采用后台线程 + 队列，避免 select 与缓冲文本 readline 混用导致的死锁。
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class EngineProc:
    """引擎子进程封装：写 stdin，按行从 stdout 队列读取。"""

    def __init__(self):
        env = dict(os.environ)
        env["SHAW_MOCK"] = "1"
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "shaw"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(ROOT),
            env=env,
            text=True,
            bufsize=1,
        )
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._stderr: list[str] = []
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._errdrain = threading.Thread(target=self._drain_stderr, daemon=True)
        self._reader.start()
        self._errdrain.start()

    def _read_stdout(self):
        try:
            for line in self.proc.stdout:
                self._lines.put(line)
        finally:
            self._lines.put(None)  # EOF 标记

    def _drain_stderr(self):
        for line in self.proc.stderr:
            self._stderr.append(line)

    def send(self, obj: dict) -> None:
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def readline(self, timeout: float = 15) -> str:
        item = self._lines.get(timeout=timeout)
        if item is None:
            raise EOFError("engine stdout closed")
        return item

    def read_events_until(self, stop_types: tuple[str, ...], timeout: float = 20) -> list[dict]:
        events = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            line = self.readline(timeout=remaining)
            ev = json.loads(line)
            events.append(ev)
            if ev.get("type") in stop_types:
                break
        return events

    @property
    def stderr_text(self) -> str:
        return "".join(self._stderr)

    def close(self):
        try:
            self.send({"jsonrpc": "2.0", "method": "shutdown", "params": {}})
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


@pytest.fixture
def engine():
    proc = EngineProc()
    yield proc
    proc.close()


def test_e2e_engine_status(engine):
    engine.send({"jsonrpc": "2.0", "id": 1, "method": "engine.status", "params": {}})
    resp = json.loads(engine.readline())
    assert resp["id"] == 1
    assert resp["result"]["status"] == "running"
    assert resp["result"]["provider"] == "mock-0.1"


def test_e2e_skill_list(engine):
    engine.send({"jsonrpc": "2.0", "id": 1, "method": "skill.list", "params": {}})
    resp = json.loads(engine.readline())
    names = {s["name"] for s in resp["result"]}
    assert {"brainstorm", "tdd", "code-review"} <= names


def test_e2e_chat_with_tool_loop(engine):
    """完整对话：mock provider 先调 Bash 工具，再用结果回复。"""
    engine.send({"jsonrpc": "2.0", "id": 5, "method": "chat.send", "params": {"message": "hello"}})

    events = engine.read_events_until(("stream_end", "error"))

    types = [e["type"] for e in events]
    assert "stream_start" in types
    assert "tool_use" in types
    assert "tool_result" in types
    assert "stream_end" in types

    # 所有事件都带 streamId 路由标记
    assert all(e.get("streamId") == 5 for e in events)

    # 工具结果应包含 mock echo 输出
    results = [e for e in events if e["type"] == "tool_result"]
    assert any("mock:hello" in e["content"] for e in results)

    # 最终文本回复
    texts = [e for e in events if e["type"] == "text"]
    assert any("Mock 回复" in e["content"] for e in texts)
