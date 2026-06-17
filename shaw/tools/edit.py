"""Edit 工具 — 精确字符串替换，支持单次与全部替换。"""

from __future__ import annotations

import os

from shaw.provider import ToolDef, ToolParam
from shaw.tools.registry import BaseTool


class EditTool(BaseTool):
    """精确替换文件中的字符串片段。"""

    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="Edit",
            description=(
                "Replace exact string occurrences in a file. By default fails on "
                "multiple matches unless replace_all is true."
            ),
            params=[
                ToolParam(name="path", type="string", description="Absolute path to the file", required=True),
                ToolParam(name="old_string", type="string", description="Exact string to replace", required=True),
                ToolParam(name="new_string", type="string", description="Replacement string", required=True),
                ToolParam(name="replace_all", type="boolean", description="Replace all occurrences", required=False),
            ],
        )

    def execute(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        if not os.path.isfile(path):
            return f"Error: File not found: {path}"

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            return f"Error reading file: {e}"

        if old_string not in content:
            return f"Error: old_string not found in {path}"

        count = content.count(old_string)
        if count > 1 and not replace_all:
            return (
                f"Error: old_string matches {count} times in {path}. "
                "Provide a more specific string or set replace_all=true."
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except OSError as e:
            return f"Error writing file: {e}"

        replaced = count if replace_all else 1
        return f"Successfully edited {path} ({replaced} replacement(s))"
