"""Tests for shaw.harness — 工具执行沙箱与安全控制。"""

import os
import tempfile

import pytest

from shaw.harness import Harness
from shaw.tools.registry import ToolRegistry
from shaw.tools.read import ReadTool
from shaw.tools.write import WriteTool
from shaw.tools.bash import BashTool


def _registry():
    r = ToolRegistry()
    r.register(ReadTool())
    r.register(WriteTool())
    r.register(BashTool())
    return r


def test_harness_creation():
    harness = Harness(tool_registry=_registry())
    assert harness is not None


def test_harness_execute():
    harness = Harness(tool_registry=_registry())
    result = harness.execute("Bash", {"command": "echo hello"})
    assert "hello" in result


def test_harness_unknown_tool():
    harness = Harness(tool_registry=ToolRegistry())
    result = harness.execute("UnknownTool", {})
    assert "error" in result.lower() or "unknown" in result.lower()


def test_harness_protected_read():
    """受保护文件被读取拦截"""
    with tempfile.NamedTemporaryFile(prefix=".env", suffix="", delete=False) as f:
        f.write(b"SECRET=xxx")
        env_path = f.name
    try:
        harness = Harness(
            tool_registry=_registry(),
            protected_patterns=[".env*"],
        )
        result = harness.execute("Read", {"path": env_path})
        assert "protected" in result.lower() or "blocked" in result.lower()
    finally:
        os.unlink(env_path)


def test_harness_protected_write():
    """受保护文件被写入拦截"""
    with tempfile.NamedTemporaryFile(prefix="id_rsa", suffix="", delete=False) as f:
        f.write(b"key")
        key_path = f.name
    try:
        harness = Harness(
            tool_registry=_registry(),
            protected_patterns=["id_*"],
        )
        result = harness.execute("Write", {"path": key_path, "content": "hacked"})
        assert "protected" in result.lower() or "blocked" in result.lower()
    finally:
        os.unlink(key_path)


def test_harness_blocked_command():
    """黑名单命令被拦截"""
    harness = Harness(
        tool_registry=_registry(),
        blocked_commands=["rm -rf /"],
    )
    result = harness.execute("Bash", {"command": "rm -rf /"})
    assert "blocked" in result.lower() or "security" in result.lower()


def test_harness_stats():
    harness = Harness(tool_registry=_registry())
    harness.execute("Bash", {"command": "echo a"})
    harness.execute("Bash", {"command": "echo b"})
    stats = harness.get_stats()
    assert stats["Bash"] == 2


def test_harness_timing():
    harness = Harness(tool_registry=_registry())
    harness.execute("Bash", {"command": "echo a"})
    timing = harness.get_timing()
    assert "Bash" in timing
    assert timing["Bash"]["count"] == 1


def test_harness_default_protected_patterns():
    """无配置时使用默认保护模式"""
    harness = Harness(tool_registry=_registry())
    with tempfile.NamedTemporaryFile(prefix=".env", suffix="", delete=False) as f:
        f.write(b"x")
        env_path = f.name
    try:
        result = harness.execute("Read", {"path": env_path})
        assert "protected" in result.lower() or "blocked" in result.lower()
    finally:
        os.unlink(env_path)
