"""Harness — 工具执行沙箱：安全控制、统计、计时。

所有工具调用经 Harness 执行，统一施加安全检查与收集指标。
"""

from __future__ import annotations

import fnmatch
import time
from typing import Any

from shaw.tools.registry import ToolRegistry

_DEFAULT_PROTECTED = [".env*", "*.pem", "id_*", "*.key", "*.p12"]
_DEFAULT_BLOCKED = ["rm -rf /", "sudo ", ":(){:|:&};:"]


class Harness:
    """工具执行环境 — 安全控制、统计、权限管理。"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        config: dict | None = None,
        protected_patterns: list[str] | None = None,
        blocked_commands: list[str] | None = None,
    ):
        self.tool_registry = tool_registry
        self.config = config or {}

        tool_config = self.config.get("tools", {})
        files_config = tool_config.get("files", {})
        bash_config = tool_config.get("bash", {})

        self.protected_patterns = (
            protected_patterns if protected_patterns is not None else files_config.get("protected_patterns", _DEFAULT_PROTECTED)
        )
        self.blocked_commands = (
            blocked_commands if blocked_commands is not None else bash_config.get("blocked_commands", _DEFAULT_BLOCKED)
        )

        self._stats: dict[str, int] = {}
        self._call_times: dict[str, list[float]] = {}

    def execute(self, tool_name: str, params: dict) -> str:
        """执行工具 — 含安全检查与统计。"""
        check = self._security_check(tool_name, params)
        if check is not None:
            return check

        start = time.perf_counter()
        result = self.tool_registry.execute(tool_name, params)
        elapsed = time.perf_counter() - start

        self._stats[tool_name] = self._stats.get(tool_name, 0) + 1
        self._call_times.setdefault(tool_name, []).append(elapsed)
        return result

    def _security_check(self, tool_name: str, params: dict) -> str | None:
        """返回错误字符串（拦截）或 None（放行）。"""
        if tool_name in ("Read", "Write", "Edit"):
            path = params.get("path", "")
            if path and self._is_protected(path):
                return f"Error: Cannot access protected file: {path}"

        if tool_name == "Bash":
            command = params.get("command", "")
            if command and self._is_blocked_command(command):
                return f"Error: Command blocked for security: {command}"

        return None

    def _is_protected(self, path: str) -> bool:
        basename = path.rsplit("/", 1)[-1]
        for pattern in self.protected_patterns:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(basename, pattern):
                return True
        return False

    def _is_blocked_command(self, command: str) -> bool:
        for blocked in self.blocked_commands:
            if blocked and blocked in command:
                return True
        return False

    def get_stats(self) -> dict[str, int]:
        return dict(self._stats)

    def get_timing(self) -> dict[str, dict[str, float]]:
        timing: dict[str, dict[str, float]] = {}
        for name, times in self._call_times.items():
            timing[name] = {
                "count": len(times),
                "total": sum(times),
                "avg": sum(times) / len(times) if times else 0,
            }
        return timing
