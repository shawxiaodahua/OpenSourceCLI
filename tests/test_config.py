"""Tests for shaw.config"""

import os
import tempfile
from pathlib import Path

import pytest

from shaw.config import load_config, get_config_path, DEFAULT_CONFIG


def test_load_config_defaults():
    """加载默认配置（无文件时返回默认值）"""
    config = load_config(path="/nonexistent/path.yaml")
    assert "provider" in config
    assert config["provider"]["default"] == "anthropic"
    assert "model" in config["provider"]["anthropic"]
    assert "tools" in config
    assert "skills" in config


def test_load_config_custom_path():
    """从指定路径加载并深度合并用户配置"""
    yaml_content = """
provider:
  anthropic:
    model: claude-sonnet-4-6-20250515
    max_tokens: 4096
session:
  max_tokens: 64000
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        config = load_config(temp_path)
        assert config["provider"]["anthropic"]["model"] == "claude-sonnet-4-6-20250515"
        assert config["provider"]["anthropic"]["max_tokens"] == 4096
        # 默认值应保留（深度合并）
        assert config["provider"]["default"] == "anthropic"
        assert config["session"]["max_tokens"] == 64000
        assert config["session"]["auto_save"] is True
    finally:
        os.unlink(temp_path)


def test_env_var_resolution(monkeypatch):
    """${ENV_VAR} 占位符被环境变量替换"""
    monkeypatch.setenv("SHAW_TEST_KEY", "sk-secret-123")
    yaml_content = """
provider:
  anthropic:
    api_key: ${SHAW_TEST_KEY}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        config = load_config(temp_path)
        assert config["provider"]["anthropic"]["api_key"] == "sk-secret-123"
    finally:
        os.unlink(temp_path)


def test_env_var_unset_returns_empty(monkeypatch):
    """未设置的环境变量解析为空字符串"""
    monkeypatch.delenv("SHAW_DEFINITELY_UNSET", raising=False)
    yaml_content = """
provider:
  anthropic:
    api_key: ${SHAW_DEFINITELY_UNSET}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        config = load_config(temp_path)
        assert config["provider"]["anthropic"]["api_key"] == ""
    finally:
        os.unlink(temp_path)


def test_get_config_path():
    """返回 ~/.shaw/config.yaml 路径对象"""
    path = get_config_path()
    assert isinstance(path, Path)
    assert path.name == "config.yaml"
    assert ".shaw" in path.parts


def test_default_config_immutable():
    """DEFAULT_CONFIG 不应被 load_config 修改"""
    original_model = DEFAULT_CONFIG["provider"]["anthropic"]["model"]
    load_config(path="/nonexistent/path.yaml")
    assert DEFAULT_CONFIG["provider"]["anthropic"]["model"] == original_model
