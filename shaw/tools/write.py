"""Write 工具 — 写入/覆盖文件，自动创建父目录。"""

from __future__ import annotations

import os

from shaw.provider import ToolDef, ToolParam
from shaw.tools.registry import BaseTool


class WriteTool(BaseTool):
    """写入文件内容，覆盖已存在文件。"""

    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="Write",
            description=(
                "Write content to a file. Creates parent directories if needed. "
                "Overwrites existing content."
            ),
            params=[
                ToolParam(name="path", type="string", description="Absolute path to the file", required=True),
                ToolParam(name="content", type="string", description="Content to write", required=True),
            ],
        )

    def execute(self, path: str, content: str) -> str:
        try:
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            size = len(content.encode("utf-8"))
            return f"Successfully wrote {size} bytes to {path}"
        except OSError as e:
            return f"Error writing file: {e}"
