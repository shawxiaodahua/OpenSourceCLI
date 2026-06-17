"""Bash 工具 — 执行 Shell 命令，带超时与输出截断。"""

from __future__ import annotations

import subprocess

from shaw.provider import ToolDef, ToolParam
from shaw.tools.registry import BaseTool

_MAX_OUTPUT = 100_000  # 100KB


class BashTool(BaseTool):
    """执行 Shell 命令。timeout 以秒为单位。"""

    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="Bash",
            description=(
                "Execute a shell command. Use to run code, build projects, or perform "
                "system operations. timeout is in seconds."
            ),
            params=[
                ToolParam(name="command", type="string", description="The command to execute", required=True),
                ToolParam(name="timeout", type="integer", description="Timeout in seconds", required=False),
            ],
        )

    def execute(self, command: str, timeout: int | None = None) -> str:
        # timeout: None → 默认 120s；统一为秒
        timeout_sec = timeout if isinstance(timeout, (int, float)) and timeout > 0 else 120
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout_sec}s"
        except OSError as e:
            return f"Error executing command: {e}"

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"

        if len(output) > _MAX_OUTPUT:
            output = output[:_MAX_OUTPUT] + f"\n... (truncated, {len(output)} total bytes)"

        return output if output else "(no output)"
