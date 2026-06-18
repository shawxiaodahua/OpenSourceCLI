"""Shaw 配置系统 — 加载 YAML 配置、解析环境变量占位符、深度合并默认值。"""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

import yaml

# 匹配 ${VAR} 形式的环境变量占位符
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

DEFAULT_CONFIG: dict[str, Any] = {
    "provider": {
        "default": "anthropic",
        "anthropic": {
            # 凭据走环境变量占位符，避免把真实/失效 key 写进源码。
            # 解析为空时，build_engine 会回退到 ANTHROPIC_AUTH_TOKEN（Claude Code 接入 Ark 时的变量）。
            "api_key": "${ANTHROPIC_API_KEY}",
            "model": "glm-5.2",
            # 单次响应的输出 token 上限，透传给 API。各模型/端点真实上限不同：
            #   glm-4 / glm-4-plus ≈ 8192；glm-4.5 / glm-4.6 ≈ 16384；
            #   claude-sonnet-4 系列 = 64000；火山 Ark `api/coding` 兼容层按 Claude 协议走。
            # 设得超过模型真实上限会触发 API 400/截断，需按所用模型下调。
            # Shaw 仅以 AnthropicProvider.MAX_TOKENS_LIMIT (128000) 做绝对兜底拦截。
            "max_tokens": 8192,
            "base_url": "https://ark.cn-beijing.volces.com/api/coding",  # 豆包 token plan 的 Claude Code 兼容端点
        },
    },
    "session": {
        # 上下文窗口预算（仅声明；当前代码未实际使用，改它无效果）。
        # 与 provider.anthropic.max_tokens（单次输出上限）是两个不同概念。
        "max_tokens": 128000,
        "auto_save": True,
    },
    "tools": {
        "bash": {
            "timeout": 120,
            "allowed_commands": [],
            "blocked_commands": ["rm -rf /", "sudo ", ":(){:|:&};:"],
        },
        "files": {
            "protected_patterns": [".env*", "*.pem", "id_*", "*.key", "*.p12"],
            "max_read_bytes": 10 * 1024 * 1024,
        },
    },
    "skills": {
        "directories": [],
        "auto_load": [],
    },
    "ui": {
        "theme": "dark",
        "code_syntax": True,
    },
}


def get_config_path() -> Path:
    """返回默认配置路径 ~/.shaw/config.yaml。"""
    return Path.home() / ".shaw" / "config.yaml"


def _resolve_env(value: Any) -> Any:
    """递归解析字符串中的 ${ENV_VAR} 占位符。

    整串为单个占位符时返回环境变量原始值；否则做字符串替换。
    未设置的变量解析为空字符串。
    """
    if isinstance(value, str):
        # 整串占位符：返回原始值（保留类型，便于未来扩展）
        full = _ENV_PATTERN.fullmatch(value)
        if full:
            return os.environ.get(full.group(1), "")
        # 否则做内联替换
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    return value


def _deep_resolve(config: Any) -> Any:
    """递归解析所有环境变量占位符。"""
    if isinstance(config, dict):
        return {k: _deep_resolve(v) for k, v in config.items()}
    if isinstance(config, list):
        return [_deep_resolve(item) for item in config]
    return _resolve_env(config)


def _deep_merge(base: dict, override: dict) -> None:
    """深度合并 override 到 base（就地修改 base）。"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载配置：以默认值为底，深度合并用户 YAML，再解析环境变量。

    文件不存在或 path 为 None 时返回解析后的默认配置。
    """
    if path is None:
        path = get_config_path()

    # 深拷贝默认配置，避免污染模块级常量
    config = copy.deepcopy(DEFAULT_CONFIG)

    path = Path(path)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        if isinstance(user_config, dict):
            _deep_merge(config, user_config)

    return _deep_resolve(config)
