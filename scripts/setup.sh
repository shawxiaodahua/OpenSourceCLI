#!/usr/bin/env bash
# Shaw CLI 初始化脚本
set -e

echo "🔧 Setting up Shaw AI CLI..."

# Python 引擎
if [ ! -d .venv ]; then
  echo "📦 创建 Python 虚拟环境..."
  python3 -m venv .venv
fi
. .venv/bin/activate
pip install -q --upgrade pip
echo "📦 安装 Python 引擎与测试依赖..."
pip install -e ".[dev]"

# CLI 依赖
if [ -d cli ]; then
  echo "📦 安装 CLI 依赖..."
  (cd cli && npm install --silent)
fi

# 配置目录
echo "📁 创建配置目录..."
mkdir -p ~/.shaw/sessions ~/.shaw/skills ~/.shaw/logs ~/.shaw/cache

cat <<'NOTE'

✅ Setup complete!

Next steps:
  1. 配置 API Key:
       export ANTHROPIC_API_KEY=sk-...
     或创建 ~/.shaw/config.yaml（见 README）
  2. 离线试运行:  SHAW_MOCK=1 python -m shaw
  3. 交互式 CLI:  cd cli && npx tsx src/index.tsx
  4. 运行测试:    python -m pytest
NOTE
