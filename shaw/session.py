"""会话管理 — 对话历史持久化与续传。"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from shaw.provider import Message


class Session:
    """一次对话会话，保存消息历史与上下文。"""

    def __init__(self, session_id: str | None = None, config: dict | None = None):
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
        self.messages: list[dict[str, Any]] = []
        self.created_at = time.time()
        self.updated_at = time.time()
        self.config = config or {}
        self.active_skill: str | None = None
        self.token_usage: dict[str, int] = {"input": 0, "output": 0}

    def add_message(self, role: str, content: Any) -> None:
        """添加一条普通消息。"""
        self.messages.append({"role": role, "content": content})
        self.updated_at = time.time()

    def add_tool_use(self, tool_name: str, tool_input: dict, tool_use_id: str, role: str = "assistant") -> dict:
        """添加 assistant 的工具调用请求块。"""
        msg = {
            "role": role,
            "content": [
                {"type": "tool_use", "id": tool_use_id, "name": tool_name, "input": tool_input}
            ],
        }
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def add_tool_result(self, tool_use_id: str, content: Any, role: str = "user") -> dict:
        """添加 user 的工具结果块。"""
        msg = {
            "role": role,
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
            ],
        }
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def to_messages(self) -> list[dict]:
        """返回可直接传给 provider 的消息列表（已与 Anthropic 格式一致）。"""
        return self.messages

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "config": self.config,
            "active_skill": self.active_skill,
            "token_usage": self.token_usage,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        s = cls(session_id=data.get("session_id"))
        s.messages = data.get("messages", [])
        s.created_at = data.get("created_at", time.time())
        s.updated_at = data.get("updated_at", time.time())
        s.config = data.get("config", {})
        s.active_skill = data.get("active_skill")
        s.token_usage = data.get("token_usage", {"input": 0, "output": 0})
        return s


class SessionManager:
    """会话管理器 — 存储与加载会话到磁盘。"""

    def __init__(self, storage_dir: str | Path | None = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".shaw" / "sessions"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session: Session) -> Path:
        path = self.storage_dir / f"{session.session_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        return path

    def load(self, session_id: str) -> Session | None:
        path = self.storage_dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return Session.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError):
            return None

    def list_sessions(self) -> list[dict]:
        sessions = []
        for path in sorted(self.storage_dir.glob("*.json"), reverse=True):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append(
                    {
                        "session_id": data.get("session_id", path.stem),
                        "created_at": data.get("created_at", 0),
                        "updated_at": data.get("updated_at", 0),
                        "message_count": len(data.get("messages", [])),
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
        return sessions

    def delete(self, session_id: str) -> bool:
        path = self.storage_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False
