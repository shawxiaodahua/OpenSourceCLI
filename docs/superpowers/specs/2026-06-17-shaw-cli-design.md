# Shaw AI CLI — 设计规格说明

> 一个开放接口的个人 AI 编程辅助 CLI 工具，类似 Claude Code / Codex CLI。
> 设计日期：2026-06-17

---

## 1. 项目概述

**Shaw** 是一个双层架构的 AI 编程辅助 CLI 工具。Python 引擎负责 LLM 循环和工具执行，Node.js TypeScript CLI 负责终端交互体验。两者通过 stdio JSON-RPC 协议通信。

### 1.1 核心目标

- 开放接口：Provider 抽象层支持多种 LLM；Tools/Skills 系统可插拔
- 功能完备：Loop、Harness、Skills 三大核心机制完整
- 个人特色：声明式技能系统、轻量级、易于扩展

### 1.2 命名

- 项目名：`Shaw`（源自作者用户名 shawxiao）
- Python 包：`shaw`
- CLI 命令：`shaw`

---

## 2. 总体架构

```
┌──────────────────────────────────────────────────────┐
│                    shaw CLI                          │
│              Node.js + TypeScript                    │
│         Ink (React for CLIs) 终端界面                │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Chat     │  │ Input    │  │ ToolCall          │  │
│  │ 组件     │  │ 组件     │  │ 组件              │  │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       │             │                  │              │
│  ┌────┴─────────────┴──────────────────┴──────────┐  │
│  │          JSON-RPC 客户端 (stdio)                │  │
│  └─────────────────────┬──────────────────────────┘  │
│                        │ stdin/stdout                │
├────────────────────────┼─────────────────────────────┤
│  ┌─────────────────────┴──────────────────────────┐  │
│  │          JSON-RPC 服务端 (stdio)                │  │
│  └────┬─────────────┬──────────────────┬──────────┘  │
│       │             │                  │              │
│  ┌────┴────┐  ┌─────┴──────┐  ┌───────┴────────┐   │
│  │ Engine  │  │ Harness    │  │ Skills         │   │
│  │ (Loop)  │  │ (Tools)    │  │ (技能系统)     │   │
│  └────┬────┘  └───────────┘  └────────────────┘   │
│       │                                             │
│  ┌────┴─────────────────────────────────────────┐   │
│  │           Provider 抽象层                     │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐     │   │
│  │  │Anthropic │ │ OpenAI   │ │ Ollama   │ ... │   │
│  │  │ (初始)   │ │ (后续)   │ │ (后续)   │     │   │
│  │  └──────────┘ └──────────┘ └──────────┘     │   │
│  └─────────────────────────────────────────────┘   │
│              shaw (Python Engine)                   │
└──────────────────────────────────────────────────────┘
```

### 2.1 通信协议

**JSON-RPC 2.0 over stdio**。CLI 启动 Python 引擎子进程，通过 stdin/stdout 双向通信。

- 请求格式：`{"jsonrpc":"2.0", "id":1, "method":"chat.send", "params":{...}}`
- 流式响应：逐行 JSON，每个对象包含 `type` 字段区分事件类型
- 通知（无响应）：`shutdown` 用于优雅关闭

**核心方法：**

| 方法 | 方向 | 说明 |
|------|------|------|
| `chat.send` | CLI → 引擎 | 发送用户消息 |
| `tool.execute` | CLI → 引擎 | 执行工具 |
| `session.create` | CLI → 引擎 | 创建新会话 |
| `session.list` | CLI → 引擎 | 列出历史会话 |
| `session.load` | CLI → 引擎 | 加载历史会话 |
| `skill.list` | CLI → 引擎 | 列出可用技能 |
| `skill.load` | CLI → 引擎 | 加载某个技能 |
| `engine.status` | CLI → 引擎 | 查询引擎状态 |
| `shutdown` (通知) | CLI → 引擎 | 优雅关闭 |

**流式事件类型：**

| 事件 | 说明 |
|------|------|
| `stream_start` | 流开始 |
| `text` | 文本片段 |
| `tool_use` | LLM 请求工具调用 |
| `tool_result` | 工具执行结果 |
| `tool_error` | 工具执行错误 |
| `thinking` | LLM 思考过程（如有） |
| `stream_end` | 流结束 |

---

## 3. Engine — LLM 循环 (Loop)

核心事件驱动循环，管理整个 AI 交互流程。

### 3.1 流程

```
用户输入
  → 技能匹配（检查 triggers）
  → 系统提示构建（基础指令 + 技能指令 + 项目上下文）
  → Provider.send() 调用 LLM
  → 流式解析事件
  → 如果是 tool_use：
      → Harness.execute() 执行工具
      → 将结果反馈给 LLM
      → 继续循环
  → 如果是 text：yield 给 CLI 渲染
  → 直到 LLM 不再请求工具调用
```

### 3.2 Session 管理

- 每个对话为一个 Session，存储在 `~/.shaw/sessions/`（JSON 文件）
- 包含：消息历史、上下文窗口、使用的技能、Token 计数
- 支持断点续传（加载历史 session）

### 3.3 上下文窗口管理

- 自动计算 Token 用量
- 超过上下文限制时自动摘要历史消息
- 用户可配置最大 Token 数

---

## 4. Provider 抽象层

所有 LLM 提供商实现统一接口：

```python
class BaseProvider(ABC):
    """LLM 提供商基类"""
    
    @abstractmethod
    async def send(
        self, 
        system: str, 
        messages: list[Message], 
        tools: list[ToolDef]
    ) -> AsyncIterator[StreamEvent]:
        ...
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        ...
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        ...
```

### 4.1 初始实现：Anthropic Claude

- 使用 Anthropic Messages API
- 支持 Thinking（扩展思考）
- 支持 Tool Use（内置函数调用）
- Streaming 逐 token 输出

### 4.2 后续扩展

- OpenAI GPT（兼容格式）
- Ollama（本地模型）
- 通过 `shaw/providers/` 目录自动发现

---

## 5. Harness — 工具执行环境

### 5.1 内置工具

| 工具名 | 说明 | 安全控制 |
|--------|------|---------|
| `Read` | 读取文件内容 | 路径白名单，敏感文件过滤 |
| `Write` | 写入/覆盖文件 | 确认大文件写入 |
| `Edit` | 精确替换文件内容 | 原子操作，备份 |
| `Bash` | 执行 Shell 命令 | 命令白名单，超时控制 |
| `Glob` | 文件模式搜索 | 限制搜索深度 |
| `Grep` | 文件内容搜索 | 限制搜索结果数量 |
| `WebSearch` | 网络搜索 | 可选 |
| `WebFetch` | 网页抓取 | 可选 |

### 5.2 安全机制

- 命令白名单/黑名单配置
- 敏感文件保护（`.env`, 密钥, `node_modules` 等）
- 执行超时控制（默认 120s）
- 输出大小限制（默认 1MB）
- 危险操作确认提示

### 5.3 扩展机制

工具通过 `shaw/tools/registry.py` 注册。第三方工具只需：

1. 实现 `BaseTool` 接口
2. 在 `shaw/tools/` 目录下注册
3. 在工具定义中声明参数 schema（JSON Schema）

---

## 6. Skills 系统 — 声明式技能

### 6.1 技能定义格式 (YAML)

```yaml
name: code-review
description: 代码审查技能
version: 1.0.0

triggers:
  - "review"
  - "代码审查"
  - "/review"

system_prompt: |
  你是一个资深代码审查者。请从以下维度审查代码：
  1. 正确性
  2. 安全性
  3. 性能
  4. 可维护性

tools:
  - Read
  - Grep
  - Bash

workflow:
  - step: 审查
    prompt: "分析代码变更..."
  - step: 验证
    condition: "有可疑代码"
    prompt: "验证假设..."

output:
  format: markdown
  template: |
    ## 审查结果
    {content}
```

### 6.2 技能加载

- 从 `skills/` 目录自动发现 `.yaml` 文件
- 支持 `~/.shaw/skills/` 用户自定义技能目录
- 运行时通过 `skill.load` 动态加载

### 6.3 技能匹配

- 用户消息匹配 `triggers` 关键词 → 自动激活
- 用户输入 `/技能名` → 显式激活
- 多个技能匹配时 → 合并系统提示（按优先级排序）

---

## 7. CLI 架构

### 7.1 技术栈

- Node.js 22 + TypeScript 5
- Ink 5（React for CLIs）
- React 19（作为 Ink 的渲染引擎）
- 依赖轻量，追求启动速度

### 7.2 组件树

```
<App>
  <Header />              # 标题栏 + 状态指示灯
  <MessageList>           # 对话消息列表（虚拟滚动）
    <UserMessage />       # 用户消息
    <AssistantMessage>    # AI 回复
      <StreamingText />   # 流式文字（打字机效果）
      <ToolCallBlock>     # 工具调用卡片
        <FileDiff />      # 文件差异展示
        <CommandOutput /> # 命令输出（折叠/展开）
      </ToolCallBlock>
    </AssistantMessage>
  </MessageList>
  <InputBar />            # 底部输入栏（支持多行）
  <StatusBar />           # 状态栏（模型/Token/模式）
  <CommandPalette />      # 命令面板（/help, /clear 等）
</App>
```

### 7.3 命令系统

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/clear` | 清屏 |
| `/model <name>` | 切换模型 |
| `/skill <name>` | 加载技能 |
| `/skills` | 列出技能 |
| `/sessions` | 列出会话 |
| `/session <id>` | 加载会话 |
| `/tokens` | 显示 Token 用量 |
| `/exit` | 退出 |

### 7.4 交互特性

- 多行输入（Shift+Enter 换行，Enter 发送）
- 快捷键绑定（Ctrl+C 中断，Ctrl+L 清屏，Tab 补全）
- 语法高亮的代码展示
- Diff 视图（类似 GitHub 的绿/红色）
- 工具调用折叠/展开
- 进度动画（流式文字、工具执行中）

---

## 8. 错误处理

| 场景 | 策略 |
|------|------|
| LLM API 超时 | 指数退避重试，3 次后提示用户 |
| API 认证失败 | 提示检查 API Key 配置 |
| Token 超限 | 自动摘要历史，或提示用户 |
| 工具执行失败 | 错误信息返回 LLM 自行修正 |
| 引擎进程崩溃 | CLI 检测退出码，自动重启 |
| 协议解析错误 | 忽略畸形行，记录日志 |
| 大文件处理 | 自动分页，只读取/写入前 N 行 |
| 网络断开 | 缓存最近的回复，重连后继续 |

---

## 9. 数据存储

```
~/.shaw/
├── config.yaml          # 用户配置（API Key, 模型, 偏好）
├── sessions/            # 会话历史
│   ├── 2026-06-17_abc123.json
│   └── ...
├── skills/              # 用户自定义技能
│   └── my-skill.yaml
├── logs/                # 引擎日志
│   └── shaw-2026-06-17.log
└── cache/               # 缓存（LLM 响应缓存等）
    └── ...
```

---

## 10. 配置系统

```yaml
# ~/.shaw/config.yaml
provider:
  default: anthropic
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: claude-sonnet-4-6
    max_tokens: 8192
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: gpt-4o

session:
  max_tokens: 128000
  auto_save: true

tools:
  bash:
    timeout: 120
    allowed_commands: ["npm", "git", "node", "python", "cargo", "go"]
    blocked_commands: ["rm -rf /", "sudo"]
  files:
    protected_patterns: [".env*", "*.pem", "id_*"]

skills:
  directories: ["~/.shaw/skills", "./skills"]
  auto_load: ["brainstorming"]

ui:
  theme: dark
  code_syntax: true
```

---

## 11. 测试策略

| 层 | 工具 | 覆盖内容 |
|----|------|---------|
| Python 单元测试 | pytest | Provider 抽象、Tool 执行、技能解析、协议 |
| Python 集成测试 | pytest + respx | LLM API mock、完整 Loop 流程 |
| Python E2E | pytest | 真实 API 调用（可选） |
| CLI 单元测试 | vitest + ink-testing-library | React 组件渲染 |
| CLI 集成测试 | vitest | JSON-RPC 客户端 |
| E2E 测试 | bash 脚本 | 完整 CLI 流程 |

---

## 12. 开发路线图

### Phase 1 — 核心引擎（MVP）
- [ ] 项目脚手架（pyproject.toml, package.json）
- [ ] Provider 抽象 + Anthropic 实现
- [ ] Engine Loop（chat.send 核心流程）
- [ ] JSON-RPC 协议实现
- [ ] 3 个基础工具（Read, Write, Bash）
- [ ] CLI 最小版本（输入框 + 流式文字输出）

### Phase 2 — 工具系统完善
- [ ] 全部内置工具（Edit, Glob, Grep, WebSearch, WebFetch）
- [ ] Harness 安全机制
- [ ] Tool 扩展注册机制

### Phase 3 — Skills 系统
- [ ] YAML 技能解析器
- [ ] 技能匹配与加载
- [ ] 技能工作流执行
- [ ] 从 Superpowers-zh 移植核心技能

### Phase 4 — CLI 体验完善
- [ ] Diff 视图
- [ ] 命令系统
- [ ] Session 管理
- [ ] 主题/配置
- [ ] 快捷键

### Phase 5 — 扩展与生态
- [ ] OpenAI Provider
- [ ] Ollama Provider
- [ ] Skills 市场/分享机制
- [ ] VS Code 扩展

---

## 13. 架构决策记录

### ADR-1: stdio JSON-RPC over HTTP
- **决策**：使用 stdio JSON-RPC 而非本地 HTTP 服务
- **理由**：无需管理端口、进程生命周期简单、延迟最低、适合 CLI 场景
- **代价**：无法多客户端共享引擎实例

### ADR-2: 声明式技能 YAML 而非编程式
- **决策**：技能使用 YAML 声明，而非 JS/Python 脚本
- **理由**：低门槛、易于分享、安全（无任意代码执行）
- **代价**：复杂逻辑受限，需要内置 workflow 引擎

### ADR-3: Python 引擎 + Node CLI
- **决策**：LLM 生态选 Python，终端体验选 Node
- **理由**：Python 的 AI 生态（LiteLLM, Tokenizer 等）无可替代；Node 的 Ink 能做出最流畅的终端 UI
- **代价**：需要维护两个代码库
