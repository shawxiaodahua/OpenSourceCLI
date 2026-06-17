"""Tests for shaw.skills — 声明式技能系统。"""

import textwrap

import pytest

from shaw.skills import Skill, SkillManager, SkillParseError


SAMPLE_YAML = """
name: code-review
description: 代码审查技能
version: "1.0.0"

triggers:
  - review
  - 代码审查
  - /review

system_prompt: |
  你是一个资深代码审查者。

tools:
  - Read
  - Grep
  - Bash

priority: 10
"""


def test_skill_parse():
    skill = Skill.from_yaml(SAMPLE_YAML)
    assert skill.name == "code-review"
    assert skill.description == "代码审查技能"
    assert skill.version == "1.0.0"
    assert "review" in skill.triggers
    assert "/review" in skill.triggers
    assert "Read" in skill.tools
    assert skill.priority == 10


def test_skill_from_file(tmp_path):
    f = tmp_path / "my.yaml"
    f.write_text(textwrap.dedent(SAMPLE_YAML), encoding="utf-8")
    skill = Skill.from_file(f)
    assert skill.name == "code-review"


def test_skill_parse_missing_name():
    with pytest.raises(SkillParseError):
        Skill.from_yaml("description: no name\n")


def test_skill_match_trigger():
    skill = Skill.from_yaml(SAMPLE_YAML)
    assert skill.matches("请 review 一下这段代码")
    assert skill.matches("做一次代码审查")
    assert skill.matches("/review")
    assert not skill.matches("今天天气不错")


def test_skill_build_system_prompt():
    skill = Skill.from_yaml(SAMPLE_YAML)
    prompt = skill.build_system_prompt()
    assert "资深代码审查者" in prompt
    assert "code-review" in prompt


def test_skill_to_summary():
    skill = Skill.from_yaml(SAMPLE_YAML)
    summary = skill.to_summary()
    assert summary["name"] == "code-review"
    assert summary["description"] == "代码审查技能"
    assert summary["triggers"] == skill.triggers


# --- SkillManager ---

def test_manager_load_directory(tmp_path):
    (tmp_path / "a.yaml").write_text(SAMPLE_YAML, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(
        "name: tdd\ndescription: TDD\ntriggers: ['/tdd', 'tdd']\nsystem_prompt: 'follow tdd'\n",
        encoding="utf-8",
    )
    (tmp_path / "not_yaml.txt").write_text("ignore me", encoding="utf-8")

    mgr = SkillManager(directories=[str(tmp_path)])
    skills = mgr.list_skills()
    names = {s.name for s in skills}
    assert names == {"code-review", "tdd"}


def test_manager_get_by_name(tmp_path):
    (tmp_path / "a.yaml").write_text(SAMPLE_YAML, encoding="utf-8")
    mgr = SkillManager(directories=[str(tmp_path)])
    assert mgr.get("code-review") is not None
    assert mgr.get("nope") is None


def test_manager_load_skill_alias(tmp_path):
    (tmp_path / "a.yaml").write_text(SAMPLE_YAML, encoding="utf-8")
    mgr = SkillManager(directories=[str(tmp_path)])
    assert mgr.load_skill("code-review") is not None


def test_manager_match_returns_highest_priority(tmp_path):
    (tmp_path / "low.yaml").write_text(
        "name: low\ndescription: low\ntriggers: ['fix']\nsystem_prompt: 'low'\npriority: 1\n",
        encoding="utf-8",
    )
    (tmp_path / "high.yaml").write_text(
        "name: high\ndescription: high\ntriggers: ['fix']\nsystem_prompt: 'high'\npriority: 100\n",
        encoding="utf-8",
    )
    mgr = SkillManager(directories=[str(tmp_path)])
    matched = mgr.match("please fix this bug")
    assert matched is not None
    assert matched.name == "high"


def test_manager_match_none(tmp_path):
    mgr = SkillManager(directories=[str(tmp_path)])
    assert mgr.match("nothing here") is None


def test_manager_explicit_slash_match(tmp_path):
    (tmp_path / "a.yaml").write_text(SAMPLE_YAML, encoding="utf-8")
    mgr = SkillManager(directories=[str(tmp_path)])
    assert mgr.match("/review") is not None
