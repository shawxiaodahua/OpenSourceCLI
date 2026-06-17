"""Glob 工具 — 文件模式搜索。"""

from __future__ import annotations

import os
from pathlib import Path

from shaw.provider import ToolDef, ToolParam
from shaw.tools.registry import BaseTool

_MAX_RESULTS = 1000


class GlobTool(BaseTool):
    """按 glob 模式搜索文件路径。"""

    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="Glob",
            description="Find files matching a glob pattern. Returns matching paths.",
            params=[
                ToolParam(name="pattern", type="string", description="Glob pattern, e.g. '**/*.py'", required=True),
                ToolParam(name="path", type="string", description="Directory to search in (default cwd)", required=False),
            ],
        )

    def execute(self, pattern: str, path: str | None = None) -> str:
        base = Path(path) if path else Path.cwd()
        if not base.exists():
            return f"Error: Path not found: {base}"

        matches = sorted(base.glob(pattern))
        if not matches:
            return f"No files matching '{pattern}' in {base}"

        rel = [str(m.relative_to(base)) if m.is_relative_to(base) else str(m) for m in matches[:_MAX_RESULTS]]
        truncated = ""
        if len(matches) > _MAX_RESULTS:
            truncated = f"\n... ({len(matches)} total, showing first {_MAX_RESULTS})"
        return "\n".join(rel) + truncated
