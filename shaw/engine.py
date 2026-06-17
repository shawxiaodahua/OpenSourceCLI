"""Shaw Engine — LLM 循环核心。

管理对话流程：技能匹配 → 系统提示构建 → Provider 调用 → 流式事件 →
工具调用反馈 → 继续循环，直到 LLM 不再请求工具。
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from shaw.provider import BaseProvider, Message
from shaw.session import Session, SessionManager
from shaw.tools.registry import ToolRegistry

DEFAULT_MAX_ITERATIONS = 25


class Engine:
    """LLM 循环引擎。"""

    def __init__(
        self,
        provider: BaseProvider,
        tools: ToolRegistry | None = None,
        harness=None,
        config: dict | None = None,
        session_manager: SessionManager | None = None,
        skills=None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ):
        self.provider = provider
        self.tools = tools or ToolRegistry()
        self.harness = harness  # None 时直接用 registry
        self.config = config or {}
        self.session_manager = session_manager or SessionManager()
        self.skills = skills
        self.max_iterations = max_iterations
        self.session: Session | None = None

    # --- 会话管理 ---

    def new_session(self) -> Session:
        self.session = Session()
        return self.session

    def load_session(self, session_id: str) -> bool:
        s = self.session_manager.load(session_id)
        if s is None:
            return False
        self.session = s
        return True

    # --- 技能 ---

    def activate_skill(self, skill) -> None:
        if self.session is None:
            self.new_session()
        self.session.active_skill = skill.name

    # --- 核心：聊天循环 ---

    async def chat(self, message: str, session_id: str | None = None) -> AsyncIterator[dict]:
        """处理用户消息，流式产出事件 dict。

        事件类型：stream_start, text, thinking, tool_use, tool_result, stream_end, error
        """
        # 加载或创建会话
        if session_id:
            loaded = self.session_manager.load(session_id)
            self.session = loaded if loaded is not None else Session(session_id=session_id)
        if self.session is None:
            self.session = Session(session_id=session_id)

        # 记录用户消息
        self.session.add_message("user", message)

        # 技能匹配（注入额外系统提示）
        skill_prompt = self._match_skill(message)

        system_prompt = self._build_system_prompt(skill_prompt)
        tool_defs = self.tools.get_tool_defs() if self.tools else []

        yield {"type": "stream_start"}

        try:
            async for _ in self._run_loop(system_prompt, tool_defs):
                yield _
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "message": f"Engine error: {e}"}

        yield {"type": "stream_end"}

        # 自动保存
        if self.config.get("session", {}).get("auto_save", True):
            self.session_manager.save(self.session)

    async def _run_loop(self, system_prompt: str, tool_defs: list) -> AsyncIterator[dict]:
        """LLM 调用循环，最多 max_iterations 轮。"""
        for _ in range(self.max_iterations):
            messages = self.session.to_messages()
            has_tool_call = False

            async for event in self.provider.send(system_prompt, [Message(m["role"], m["content"]) for m in messages], tool_defs or None):
                if event.type == "text":
                    yield {"type": "text", "content": event.content}
                elif event.type == "thinking":
                    yield {"type": "thinking", "content": event.content}
                elif event.type == "tool_use":
                    has_tool_call = True
                    yield {
                        "type": "tool_use",
                        "name": event.tool_name,
                        "input": event.tool_input,
                        "id": event.tool_use_id,
                    }
                    # 记录 assistant 工具调用块
                    self.session.add_tool_use(event.tool_name, event.tool_input, event.tool_use_id)

                    # 执行工具
                    result = self._execute_tool(event.tool_name, event.tool_input)
                    is_error = isinstance(result, str) and result.startswith("Error")
                    self.session.add_tool_result(event.tool_use_id, result)

                    yield {
                        "type": "tool_result",
                        "id": event.tool_use_id,
                        "content": result,
                        "is_error": is_error,
                    }
                elif event.type == "done":
                    pass  # 单轮结束，由 has_tool_call 决定是否继续

            if not has_tool_call:
                break

    def _execute_tool(self, name: str, params: dict) -> str:
        """通过 harness（若有）或直接 registry 执行工具。"""
        if self.harness is not None:
            return self.harness.execute(name, params)
        return self.tools.execute(name, params)

    # --- 系统提示 ---

    def _match_skill(self, message: str) -> str:
        """匹配技能，返回额外系统提示（无匹配返回空串）。"""
        if self.skills is None:
            return ""
        skill = self.skills.match(message)
        if skill is None:
            return ""
        self.session.active_skill = skill.name
        return skill.build_system_prompt()

    def _build_system_prompt(self, skill_prompt: str = "") -> str:
        parts = [
            "You are Shaw, a personal AI programming assistant running in the terminal.",
            "You help with coding tasks: reading, writing, and editing code, running commands, and debugging.",
            "",
            "Available tools:",
        ]
        for name in (self.tools.list() if self.tools else []):
            parts.append(f"- {name}")
        parts += [
            "",
            "Guidelines:",
            "- Show the code you write or modify.",
            "- Explain reasoning briefly.",
            "- Use tools to verify your work when appropriate.",
            "- When you encounter errors, fix them before moving on.",
            "- Prefer targeted edits over rewriting whole files.",
        ]
        if skill_prompt:
            parts += ["", "=== Active skill ===", skill_prompt]
        return "\n".join(parts)

    async def shutdown(self) -> None:
        if self.session is not None:
            self.session_manager.save(self.session)
