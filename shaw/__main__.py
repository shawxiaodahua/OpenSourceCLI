"""Shaw CLI 引擎入口 — 通过 stdio JSON-RPC 提供服务。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from shaw.config import load_config
from shaw.engine import Engine
from shaw.harness import Harness
from shaw.protocol import JsonRpcServer
from shaw.providers.anthropic import AnthropicProvider
from shaw.providers.mock import MockProvider
from shaw.session import SessionManager
from shaw.skills import SkillManager
from shaw.tools.bash import BashTool
from shaw.tools.edit import EditTool
from shaw.tools.glob import GlobTool
from shaw.tools.grep import GrepTool
from shaw.tools.read import ReadTool
from shaw.tools.registry import ToolRegistry
from shaw.tools.webfetch import WebFetchTool
from shaw.tools.write import WriteTool


def build_engine(config: dict | None = None) -> Engine:
    """根据配置构建完整引擎：Provider + 全部工具 + Harness + Skills。"""
    config = config or load_config()

    import os

    provider_name = os.environ.get("SHAW_PROVIDER") or config["provider"]["default"]

    if provider_name == "mock" or os.environ.get("SHAW_MOCK") == "1":
        provider = MockProvider()
    else:
        provider_cfg = config["provider"][provider_name]
        # 凭据优先级：config(已解析 ${ANTHROPIC_API_KEY}) > ANTHROPIC_AUTH_TOKEN 环境变量。
        # 后者是 Claude Code 接入火山方舟/豆包时的标准变量，配置文件未提供 key 时回退到它。
        api_key = provider_cfg.get("api_key", "") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        provider = AnthropicProvider(
            api_key=api_key,
            model=provider_cfg.get("model", "claude-sonnet-4-6-20250515"),
            max_tokens=provider_cfg.get("max_tokens", 8192),
            base_url=provider_cfg.get("base_url"),
        )
        # 后台预热 anthropic SDK 导入（消除首条消息的数秒卡顿）
        provider.preload()

    # 注册全部内置工具
    registry = ToolRegistry()
    for tool in (
        ReadTool(),
        WriteTool(),
        EditTool(),
        BashTool(),
        GlobTool(),
        GrepTool(),
        WebFetchTool(),
    ):
        registry.register(tool)

    # Harness：安全控制 + 统计
    harness = Harness(tool_registry=registry, config=config)

    # Skills：用户目录 + 内置 skills 目录
    skill_dirs = list(config.get("skills", {}).get("directories", []))
    builtin_skills = Path(__file__).resolve().parent.parent / "skills"
    if builtin_skills.exists():
        skill_dirs.append(str(builtin_skills))
    skills = SkillManager(directories=skill_dirs)

    session_manager = SessionManager()

    return Engine(
        provider=provider,
        tools=registry,
        harness=harness,
        config=config,
        session_manager=session_manager,
        skills=skills,
    )


async def main() -> None:
    config = load_config()
    engine = build_engine(config)
    server = JsonRpcServer(engine=engine)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
