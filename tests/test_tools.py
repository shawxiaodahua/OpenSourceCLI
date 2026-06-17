"""Tests for shaw.tools — 注册表与内置工具。"""

import os
import tempfile

import pytest

from shaw.tools.registry import ToolRegistry, BaseTool
from shaw.tools.read import ReadTool
from shaw.tools.write import WriteTool
from shaw.tools.edit import EditTool
from shaw.tools.bash import BashTool
from shaw.tools.glob import GlobTool
from shaw.tools.grep import GrepTool


# --- 注册表 ---

def test_tool_registry():
    registry = ToolRegistry()
    tool = ReadTool()
    registry.register(tool)
    assert registry.get("Read") is tool
    assert registry.list() == ["Read"]
    defs = registry.get_tool_defs()
    assert defs[0].name == "Read"


def test_registry_execute_unknown():
    registry = ToolRegistry()
    result = registry.execute("Nope", {})
    assert "error" in result.lower() or "unknown" in result.lower()


# --- Read ---

def test_read_tool():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line1\nline2\nline3\n")
        temp_path = f.name
    try:
        result = ReadTool().execute(path=temp_path)
        assert "line1" in result and "line2" in result and "line3" in result
    finally:
        os.unlink(temp_path)


def test_read_with_offset_limit():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\nd\ne\n")
        temp_path = f.name
    try:
        result = ReadTool().execute(path=temp_path, offset=2, limit=2)
        # 第 2-3 行
        assert "b" in result and "c" in result
        assert "a" not in result.split("\n")[-1]  # offset 之后不含第一行
    finally:
        os.unlink(temp_path)


def test_read_nonexistent_file():
    result = ReadTool().execute(path="/nonexistent/file.txt")
    assert "error" in result.lower() or "not found" in result.lower()


# --- Write ---

def test_write_tool():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        temp_path = f.name
    try:
        result = WriteTool().execute(path=temp_path, content="new content")
        assert "wrote" in result.lower() or "success" in result.lower()
        with open(temp_path) as f:
            assert f.read() == "new content"
    finally:
        os.unlink(temp_path)


def test_write_creates_parent_dirs(tmp_path):
    target = tmp_path / "sub" / "deep" / "file.txt"
    WriteTool().execute(path=str(target), content="x")
    assert target.read_text() == "x"


# --- Edit ---

def test_edit_replace():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello world\nfoo bar\n")
        temp_path = f.name
    try:
        EditTool().execute(path=temp_path, old_string="world", new_string="earth")
        with open(temp_path) as f:
            content = f.read()
        assert "hello earth" in content
        assert "world" not in content
    finally:
        os.unlink(temp_path)


def test_edit_not_found():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello\n")
        temp_path = f.name
    try:
        result = EditTool().execute(path=temp_path, old_string="nope", new_string="x")
        assert "error" in result.lower() or "not found" in result.lower()
    finally:
        os.unlink(temp_path)


def test_edit_multiple_matches_error():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("dup\ndup\n")
        temp_path = f.name
    try:
        result = EditTool().execute(path=temp_path, old_string="dup", new_string="x")
        assert "error" in result.lower() or "multiple" in result.lower()
    finally:
        os.unlink(temp_path)


def test_edit_replace_all():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("dup\ndup\n")
        temp_path = f.name
    try:
        EditTool().execute(path=temp_path, old_string="dup", new_string="x", replace_all=True)
        with open(temp_path) as f:
            assert f.read() == "x\nx\n"
    finally:
        os.unlink(temp_path)


# --- Bash ---

def test_bash_tool():
    result = BashTool().execute(command="echo hello")
    assert "hello" in result


def test_bash_tool_exit_code():
    result = BashTool().execute(command="exit 3")
    assert "3" in result


def test_bash_tool_timeout():
    # timeout 以秒为单位；sleep 远超之
    result = BashTool().execute(command="sleep 10", timeout=1)
    assert "timeout" in result.lower() or "timed out" in result.lower()


# --- Glob ---

def test_glob_tool(tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.txt").write_text("y")
    result = GlobTool().execute(path=str(tmp_path), pattern="*.py")
    assert "a.py" in result
    assert "b.txt" not in result


# --- Grep ---

def test_grep_tool(tmp_path):
    (tmp_path / "f.txt").write_text("alpha\nbeta\ngamma\n")
    result = GrepTool().execute(path=str(tmp_path), pattern="beta")
    assert "beta" in result


def test_grep_no_match(tmp_path):
    (tmp_path / "f.txt").write_text("alpha\n")
    result = GrepTool().execute(path=str(tmp_path), pattern="zzz")
    assert "no match" in result.lower() or "0" in result or result.strip() == ""
