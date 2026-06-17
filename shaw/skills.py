"""Skills 声明式技能系统 — YAML 定义、自动发现、trigger 匹配。

技能文件格式（YAML）：

    name: code-review          # 必填
    description: 代码审查技能    # 必填
    version: "1.0.0"           # 可选
    triggers:                  # 触发关键词（子串匹配，/ 前缀显式触发）
      - review
      - /review
    system_prompt: |           # 注入到系统提示
      你是一个资深代码审查者。
    tools:                     # 该技能允许使用的工具子集（仅文档化，不强制）
      - Read
      - Grep
    priority: 10               # 多技能匹配时按优先级排序，默认 0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class SkillParseError(Exception):
    """技能解析错误。"""


@dataclass
class Skill:
    """一个声明式技能。"""

    name: str
    description: str
    version: str = "0.1.0"
    triggers: list[str] = field(default_factory=list)
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    workflow: list[dict] = field(default_factory=list)
    priority: int = 0
    source: str = ""

    @classmethod
    def from_yaml(cls, text: str, source: str = "") -> "Skill":
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            raise SkillParseError(f"YAML 解析失败: {e}") from e

        if not isinstance(data, dict):
            raise SkillParseError("技能文件必须是 YAML 映射")
        if not data.get("name"):
            raise SkillParseError("技能缺少必填字段: name")
        if not data.get("description"):
            raise SkillParseError(f"技能 {data['name']} 缺少必填字段: description")

        return cls(
            name=data["name"],
            description=data["description"],
            version=str(data.get("version", "0.1.0")),
            triggers=list(data.get("triggers", []) or []),
            system_prompt=data.get("system_prompt", "") or "",
            tools=list(data.get("tools", []) or []),
            workflow=list(data.get("workflow", []) or []),
            priority=int(data.get("priority", 0) or 0),
            source=source,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "Skill":
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            return cls.from_yaml(f.read(), source=str(path))

    def matches(self, message: str) -> bool:
        """消息是否匹配某 trigger（子串匹配，大小写不敏感）。"""
        lower = message.lower()
        return any(t.lower() in lower for t in self.triggers)

    def build_system_prompt(self) -> str:
        """构建该技能注入到系统提示的文本。"""
        parts = [f"[Skill: {self.name}]", self.description]
        if self.system_prompt:
            parts.append(self.system_prompt.strip())
        if self.tools:
            parts.append("建议工具: " + ", ".join(self.tools))
        return "\n".join(parts)

    def to_summary(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "triggers": self.triggers,
            "priority": self.priority,
        }


class SkillManager:
    """技能管理器 — 从多个目录自动发现并加载技能。"""

    def __init__(self, directories: list[str] | None = None):
        self.directories: list[Path] = [Path(d) for d in (directories or [])]
        self._skills: dict[str, Skill] = {}
        self.reload()

    def reload(self) -> None:
        """重新扫描所有目录，加载技能。"""
        self._skills.clear()
        for d in self.directories:
            if not d.exists():
                continue
            for path in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
                try:
                    skill = Skill.from_file(path)
                except SkillParseError:
                    continue
                # 后加载的优先级更高（覆盖同名）
                self._skills[skill.name] = skill

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def load_skill(self, name: str) -> Skill | None:
        """显式加载技能（/skill <name>）。支持去掉前导 /。"""
        if name.startswith("/"):
            name = name[1:]
        return self.get(name)

    def match(self, message: str) -> Skill | None:
        """返回匹配的最高优先级技能，无匹配返回 None。"""
        candidates = [s for s in self._skills.values() if s.matches(message)]
        if not candidates:
            return None
        candidates.sort(key=lambda s: s.priority, reverse=True)
        return candidates[0]
