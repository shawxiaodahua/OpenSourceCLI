"""工具注册表 — 管理所有可用工具的注册、查找与执行。"""

from __future__ import annotations

from typing import Any

from shaw.provider import ToolDef, ToolParam


class BaseTool:
    """工具基类。子类需实现 tool_def 与 execute。"""

    @property
    def name(self) -> str:
        """工具名，默认取类名去掉 Tool 后缀。"""
        cls_name = self.__class__.__name__
        return cls_name[:-4] if cls_name.endswith("Tool") else cls_name

    @property
    def tool_def(self) -> ToolDef:
        """返回工具定义（用于 LLM 函数调用声明）。"""
        raise NotImplementedError

    def execute(self, **kwargs) -> str:
        """执行工具，返回结果字符串。"""
        raise NotImplementedError


class ToolRegistry:
    """工具注册表 — 管理所有可用工具。"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> "ToolRegistry":
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list(self) -> list[str]:
        return list(self._tools.keys())

    def get_tool_defs(self) -> list[ToolDef]:
        return [tool.tool_def for tool in self._tools.values()]

    def execute(self, name: str, params: dict) -> str:
        tool = self.get(name)
        if tool is None:
            return f"Error: Unknown tool '{name}'"
        try:
            return tool.execute(**params)
        except TypeError as e:
            return f"Error: Invalid params for {name}: {e}"
        except Exception as e:  # noqa: BLE001
            return f"Error executing {name}: {e}"
