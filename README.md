# Shaw AI CLI

> 个人 AI 编程辅助 CLI 工具 — 开放接口，功能完备。
> 类似 Claude Code / Codex CLI / AtomCode CLI，注重个人开发特色与可扩展性。

Shaw 采用**双层架构**：Python 引擎负责 LLM 循环与工具执行，Node.js + Ink CLI 负责终端交互，两者通过 **stdio JSON-RPC** 通信。三大核心机制（Loop / Harness / Skills）均以开放接口形式提供。

## 架构

```
┌──────────────────────────────────────────────────────┐
│              shaw CLI  (Node.js + Ink)               │
│   Chat / Input / ToolCall 组件  ←→  JSON-RPC 客户端   │
├──────────────────────────────────────────────────────┤
│              shaw 引擎  (Python)                      │
│   Engine(Loop)  →  Harness(工具沙箱)  →  Skills        │
│                  ↓                                    │
│            Provider 抽象层                             │
│   Anthropic · Mock · (可扩展 OpenAI/Ollama)           │
└──────────────────────────────────────────────────────┘
        通信：JSON-RPC 2.0 over stdio
```

## 核心机制

### Loop — LLM 循环 (`shaw/engine.py`)
事件驱动循环：技能匹配 → 系统提示构建 → Provider 调用 → 流式解析 → 工具调用反馈 → 继续循环，直到 LLM 不再请求工具。带最大迭代次数保护与上下文窗口管理。

### Harness — 工具执行沙箱 (`shaw/harness.py`)
统一施加安全控制（受保护文件、命令黑名单）、超时、输出截断，并收集调用统计与计时。所有工具调用经 Harness 执行。

### Skills — 声明式技能 (`shaw/skills.py`)
YAML 定义技能：`triggers` 关键词匹配、`system_prompt` 注入、`tools` 子集、`priority` 优先级。从多个目录自动发现，支持 `/技能名` 显式激活与子串自动匹配。

## 内置工具

| 工具 | 说明 |
|------|------|
| Read | 读取文件内容（带行号、offset/limit） |
| Write | 写入文件（自动建父目录） |
| Edit | 精确字符串替换（单次/全部） |
| Bash | 执行 Shell 命令（超时、输出截断） |
| Glob | 文件模式搜索 |
| Grep | 内容搜索（ripgrep 优先，回退纯 Python） |
| WebFetch | 抓取网页并提取文本 |

## 快速开始

### 前置要求
- Python ≥ 3.11
- Node.js ≥ 22

### 安装

```bash
# Python 引擎（可编辑模式 + 测试依赖）
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# CLI 依赖
cd cli && npm install && cd ..
```

### 配置

```bash
mkdir -p ~/.shaw
cat > ~/.shaw/config.yaml << 'EOF'
provider:
  default: anthropic
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-sonnet-4-6-20250515
    max_tokens: 8192
    # base_url: https://your-proxy.example.com   # 可选，自定义端点
EOF
export ANTHROPIC_API_KEY=sk-...
```

### 离线试运行（无需 API Key）

```bash
SHAW_MOCK=1 shaw   # 引擎走 MockProvider，演示完整工具调用循环
```

### 启动

```bash
# 方式一：直接运行引擎（stdio JSON-RPC）
python -m shaw

# 方式二：交互式 CLI（在真实终端中）
cd cli && npx tsx src/index.tsx
# 或指定引擎：
SHAW_PYTHON=$(pwd)/../.venv/bin/python npx tsx src/index.tsx
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/status` | 引擎状态 |
| `/skills` | 列出技能 |
| `/clear` | 清屏 |
| `/exit` | 退出 |
| `Ctrl+C` | 中断并退出 |

## 扩展

### 添加 Provider
在 `shaw/providers/` 下实现 `BaseProvider`，在 `build_engine` 中按 `provider.default` 选择。

### 添加工具
在 `shaw/tools/` 下继承 `BaseTool`，实现 `tool_def` 与 `execute`，在 `build_engine` 中注册。

### 添加技能
在 `skills/` 或 `~/.shaw/skills/` 下放 YAML 文件：

```yaml
name: my-skill
description: 我的技能
triggers: ["/my", "我的技能"]
system_prompt: |
  你是一个……
tools: [Read, Bash]
priority: 5
```

## 数据目录

```
~/.shaw/
├── config.yaml     # 用户配置
├── sessions/       # 会话历史（断点续传）
├── skills/         # 用户自定义技能
└── logs/           # 日志
```

## 测试

```bash
. .venv/bin/activate
python -m pytest                    # 全部测试（含端到端）
python -m pytest tests/test_e2e.py  # 端到端（spawn 真实引擎 + Mock）
```

CLI 类型检查：
```bash
cd cli && npx tsc --noEmit
```

## 项目结构

```
shaw/                  # Python 引擎
  engine.py            # LLM 循环核心
  harness.py           # 工具执行沙箱
  provider.py          # Provider 抽象层
  protocol.py          # JSON-RPC 协议
  session.py           # 会话管理
  skills.py            # 声明式技能系统
  providers/           # anthropic / mock
  tools/               # read/write/edit/bash/glob/grep/webfetch
cli/                   # Node.js CLI
  src/rpc.ts           # JSON-RPC 客户端（单 readline 多路解复用）
  src/index.tsx        # 入口
  src/components/      # App / MessageList / ToolCall
skills/                # 内置技能（brainstorm/tdd/code-review）
tests/                 # pytest 测试
```

## 设计决策

- **stdio JSON-RPC 而非 HTTP**：无需管理端口、进程生命周期简单、延迟最低。
- **声明式技能 YAML 而非编程式**：低门槛、易分享、安全（无任意代码执行）。
- **Python 引擎 + Node CLI**：Python AI 生态成熟，Ink 终端体验最佳。
- **MockProvider + SHAW_MOCK**：离线可跑通完整链路，便于开发与测试。

## License

MIT
