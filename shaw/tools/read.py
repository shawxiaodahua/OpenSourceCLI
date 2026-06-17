"""Read 工具 — 读取文件内容，带行号。"""

from __future__ import annotations

import os

from shaw.provider import ToolDef, ToolParam
from shaw.tools.registry import BaseTool

_MAX_BYTES = 10 * 1024 * 1024  # 10MB


class ReadTool(BaseTool):
    """读取文件内容，行号从 1 开始。"""

    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="Read",
            description=(
                "Read the contents of a file. Lines are numbered starting from 1. "
                "Use offset/limit for large files."
            ),
            params=[
                ToolParam(name="path", type="string", description="Absolute path to the file", required=True),
                ToolParam(name="offset", type="integer", description="Line number to start reading from (1-based)", required=False),
                ToolParam(name="limit", type="integer", description="Number of lines to read", required=False),
            ],
        )

    def execute(self, path: str, offset: int = 0, limit: int = 2000) -> str:
        if not os.path.exists(path):
            return f"Error: File not found: {path}"
        if not os.path.isfile(path):
            return f"Error: Not a file: {path}"

        size = os.path.getsize(path)
        if size > _MAX_BYTES:
            return f"Error: File too large ({size / 1024 / 1024:.1f}MB). Maximum: {_MAX_BYTES // 1024 // 1024}MB"

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            return f"Error reading file: {e}"

        total = len(lines)
        start = max(0, (offset - 1) if offset > 0 else 0)
        end = min(start + limit, total)

        if start >= total:
            return f"File has {total} lines, but offset {offset} is beyond end."

        rendered = []
        for i in range(start, end):
            rendered.append(f"{i + 1}\t{lines[i].rstrip()}")

        body = "\n".join(rendered)
        return f"File: {path} ({total} lines, showing {start + 1}-{end})\n{body}"
