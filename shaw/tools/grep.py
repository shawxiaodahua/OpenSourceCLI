"""Grep 工具 — 文件内容搜索（基于 ripgrep 优先，回退纯 Python）。"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from shaw.provider import ToolDef, ToolParam
from shaw.tools.registry import BaseTool

_MAX_RESULTS = 200


class GrepTool(BaseTool):
    """在文件中搜索正则/字面量，返回匹配行。"""

    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="Grep",
            description="Search file contents for a pattern (regex). Returns matching lines with file:line.",
            params=[
                ToolParam(name="pattern", type="string", description="Regex pattern", required=True),
                ToolParam(name="path", type="string", description="File or directory to search in (default cwd)", required=False),
                ToolParam(name="glob", type="string", description="File glob filter, e.g. '*.py'", required=False),
            ],
        )

    def execute(self, pattern: str, path: str | None = None, glob: str | None = None) -> str:
        base = Path(path) if path else Path.cwd()
        if not base.exists():
            return f"Error: Path not found: {base}"

        # 优先使用 ripgrep（更快、更好）
        if shutil.which("rg"):
            return self._grep_with_rg(pattern, base, glob)

        return self._grep_python(pattern, base, glob)

    def _grep_with_rg(self, pattern: str, base: Path, glob: str | None) -> str:
        cmd = ["rg", "--line-number", "--no-heading", "--color=never", "-m", str(_MAX_RESULTS)]
        if glob:
            cmd += ["-g", glob]
        cmd += [pattern, str(base)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (subprocess.TimeoutExpired, OSError) as e:
            return f"Error running rg: {e}"

        out = result.stdout.strip()
        if not out:
            return "No matches found"
        lines = out.splitlines()
        if len(lines) > _MAX_RESULTS:
            lines = lines[:_MAX_RESULTS] + [f"... ({len(lines)} total, showing first {_MAX_RESULTS})"]
        return "\n".join(lines)

    def _grep_python(self, pattern: str, base: Path, glob: str | None) -> str:
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Error: Invalid regex: {e}"

        files: list[Path]
        if base.is_file():
            files = [base]
        else:
            files = [p for p in base.rglob("*") if p.is_file()]
            if glob:
                from fnmatch import fnmatch

                files = [p for p in files if fnmatch(p.name, glob)]

        matches: list[str] = []
        for fp in files:
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, start=1):
                        if regex.search(line):
                            matches.append(f"{fp}:{lineno}:{line.rstrip()}")
                            if len(matches) >= _MAX_RESULTS:
                                matches.append(f"... (truncated at {_MAX_RESULTS} matches)")
                                return "\n".join(matches)
            except OSError:
                continue

        if not matches:
            return "No matches found"
        return "\n".join(matches)
