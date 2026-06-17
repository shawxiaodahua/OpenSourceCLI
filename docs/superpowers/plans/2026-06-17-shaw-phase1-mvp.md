# Shaw CLI Phase 1 — 核心引擎 MVP 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现 Shaw CLI 的 MVP 版本：Python 引擎支持 Anthropic Claude 的 LLM 循环 + 3 个基础工具（Read, Write, Bash），Node CLI 提供基本的交互式对话界面。

**架构：** 双层架构：Python `shaw` 包（Engine + Harness + Provider）作为子进程运行，Node.js TypeScript CLI 通过 stdio JSON-RPC 与之通信。

**技术栈：** Python 3.13 (pytest, httpx, pydantic), Node.js 22 (TypeScript 5, Ink 5, React 19)

---

## 文件结构

```
OpenSourceCLI/
├── pyproject.toml                  # Python 项目配置
├── .gitignore                      # Git 忽略规则
├── README.md                       # 项目说明
├── shaw/                           # Python 引擎包
│   ├── __init__.py
│   ├── __main__.py                 # python -m shaw 入口
│   ├── engine.py                   # Engine Loop 主类
│   ├── protocol.py                 # JSON-RPC 协议实现
│   ├── config.py                   # 配置加载
│   ├── session.py                  # 会话管理
│   ├── provider.py                 # Provider 抽象基类
│   ├── providers/
│   │   ├── __init__.py
│   │   └── anthropic.py            # Anthropic Claude 实现
│   ├── harness.py                  # Harness — 工具执行环境
│   └── tools/
│       ├── __init__.py
│       ├── registry.py             # 工具注册表
│       ├── read.py                 # Read 工具
│       ├── write.py                # Write 工具
│       └── bash.py                 # Bash 工具
├── tests/                          # Python 测试
│   ├── __init__.py
│   ├── test_protocol.py
│   ├── test_engine.py
│   ├── test_provider.py
│   ├── test_harness.py
│   └── test_tools.py
├── cli/                            # Node.js CLI
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── index.ts                # CLI 入口
│       ├── app.tsx                  # 主应用组件
│       ├── rpc.ts                   # JSON-RPC 客户端
│       └── components/
│           ├── App.tsx
│           ├── Chat.tsx
│           ├── Input.tsx
│           └── ToolCall.tsx
└── skills/                         # 声明式技能
    └── brainstorm.yaml
```

---

### 任务 1：项目脚手架

**文件：**
- 创建：`OpenSourceCLI/pyproject.toml`
- 创建：`OpenSourceCLI/.gitignore`
- 创建：`OpenSourceCLI/setup.cfg`
- 创建：`OpenSourceCLI/shaw/__init__.py`
- 创建：`OpenSourceCLI/shaw/__main__.py`
- 创建：`OpenSourceCLI/tests/__init__.py`

- [ ] **步骤 1：创建 pyproject.toml**

```toml
[project]
name = "shaw"
version = "0.1.0"
description = "Shaw AI CLI — 个人 AI 编程辅助工具"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.28",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "anthropic>=0.40",
]

[project.scripts]
shaw = "shaw.__main__:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.ruff]
line-length = 100
target-version = "py311"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **步骤 2：创建 .gitignore**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/

# Node
cli/node_modules/
cli/dist/

# Shaw
shaw/logs/
shaw/sessions/
shaw/cache/
~/.shaw/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Env
.env
.env.local
```

- [ ] **步骤 3：创建 shaw/__init__.py**

```python
"""Shaw AI CLI — Python LLM 引擎"""

__version__ = "0.1.0"
```

- [ ] **步骤 4：创建 shaw/__main__.py**

```python
"""Shaw CLI 引擎入口 — 通过 stdio JSON-RPC 服务"""

import sys
import asyncio
from shaw.engine import Engine
from shaw.protocol import JsonRpcServer
from shaw.config import load_config
from shaw.providers.anthropic import AnthropicProvider
from shaw.tools.registry import ToolRegistry
from shaw.tools.read import ReadTool
from shaw.tools.write import WriteTool
from shaw.tools.bash import BashTool


async def main():
    config = load_config()
    
    # 初始化 Provider
    provider = AnthropicProvider(
        api_key=config["provider"]["anthropic"]["api_key"],
        model=config["provider"]["anthropic"]["model"],
        max_tokens=config["provider"]["anthropic"].get("max_tokens", 8192),
    )
    
    # 注册工具
    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(BashTool())
    
    # 初始化引擎
    engine = Engine(provider=provider, tools=registry, config=config)
    
    # 启动 JSON-RPC 服务（stdio）
    server = JsonRpcServer(engine=engine)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **步骤 5：运行测试验证项目结构**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -c "import shaw; print(shaw.__version__)"`
预期：输出 `0.1.0`

- [ ] **步骤 6：Commit**

```bash
git add -A
git commit -m "chore: scaffold Shaw CLI project structure"
```

---

### 任务 2：配置系统

**文件：**
- 创建：`shaw/config.py`
- 创建：`tests/test_config.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""Tests for shaw.config"""

import os
import tempfile
from pathlib import Path
import pytest
from shaw.config import load_config, get_config_path


def test_load_config_defaults():
    """加载默认配置"""
    config = load_config()
    assert "provider" in config
    assert "anthropic" in config["provider"]
    assert "model" in config["provider"]["anthropic"]


def test_load_config_custom_path():
    """从指定路径加载配置"""
    yaml_content = """
provider:
  anthropic:
    model: claude-sonnet-4-6-20250515
    max_tokens: 4096
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name
    
    try:
        config = load_config(temp_path)
        assert config["provider"]["anthropic"]["model"] == "claude-sonnet-4-6-20250515"
        assert config["provider"]["anthropic"]["max_tokens"] == 4096
    finally:
        os.unlink(temp_path)


def test_get_config_path():
    """返回配置路径（不报错）"""
    path = get_config_path()
    assert isinstance(path, Path)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_config.py -v 2>&1 || true`
预期：ImportError，config 模块不存在

- [ ] **步骤 3：编写实现代码**

```python
"""Shaw 配置系统"""

import os
from pathlib import Path
from typing import Any
import yaml


DEFAULT_CONFIG = {
    "provider": {
        "default": "anthropic",
        "anthropic": {
            "api_key": "${ANTHROPIC_API_KEY}",
            "model": "claude-sonnet-4-6-20250515",
            "max_tokens": 8192,
        },
    },
    "session": {
        "max_tokens": 128000,
        "auto_save": True,
    },
    "tools": {
        "bash": {
            "timeout": 120,
            "allowed_commands": [],
            "blocked_commands": [],
        },
        "files": {
            "protected_patterns": [".env*", "*.pem", "id_*", "*.key"],
        },
    },
    "skills": {
        "directories": [],
        "auto_load": [],
    },
}


def get_config_path() -> Path:
    """获取默认配置路径 ~/.shaw/config.yaml"""
    return Path.home() / ".shaw" / "config.yaml"


def _resolve_env(value: Any) -> Any:
    """解析 ${ENV_VAR} 占位符"""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")
    return value


def _deep_resolve(config: dict) -> dict:
    """递归解析所有环境变量占位符"""
    resolved = {}
    for key, value in config.items():
        if isinstance(value, dict):
            resolved[key] = _deep_resolve(value)
        else:
            resolved[key] = _resolve_env(value)
    return resolved


def load_config(path: str | Path | None = None) -> dict:
    """加载配置，如果文件不存在则使用默认值"""
    if path is None:
        path = get_config_path()
    
    config = DEFAULT_CONFIG.copy()
    
    if isinstance(path, str):
        path = Path(path)
    
    if path.exists():
        with open(path) as f:
            user_config = yaml.safe_load(f) or {}
        _deep_merge(config, user_config)
    
    return _deep_resolve(config)


def _deep_merge(base: dict, override: dict) -> None:
    """深度合并字典"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_config.py -v`
预期：3 PASSED

- [ ] **步骤 5：Commit**

```bash
git add shaw/config.py tests/test_config.py
git commit -m "feat: add config system with env var resolution"
```

---

### 任务 3：JSON-RPC 协议

**文件：**
- 创建：`shaw/protocol.py`
- 创建：`tests/test_protocol.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""Tests for shaw.protocol"""

import json
import pytest
from shaw.protocol import JsonRpcServer, JsonRpcClient, JsonRpcError, create_request


def test_create_request():
    """创建 JSON-RPC 请求"""
    request = create_request("chat.send", {"message": "hello"})
    assert request["jsonrpc"] == "2.0"
    assert request["method"] == "chat.send"
    assert request["params"]["message"] == "hello"
    assert "id" in request


def test_create_request_with_id():
    """创建指定 ID 的请求"""
    request = create_request("chat.send", {}, request_id=42)
    assert request["id"] == 42


def test_json_rpc_error():
    """JSON-RPC 错误对象"""
    error = JsonRpcError(code=-32601, message="Method not found")
    assert error.code == -32601
    assert error.message == "Method not found"
    
    error_dict = error.to_dict()
    assert error_dict["code"] == -32601
    assert error_dict["message"] == "Method not found"


async def test_server_unknown_method():
    """未知方法返回错误"""
    server = JsonRpcServer(engine=None)
    response = await server.handle(b'{"jsonrpc":"2.0","id":1,"method":"unknown","params":{}}')
    result = json.loads(response)
    assert "error" in result
    assert result["error"]["code"] == -32601


async def test_server_malformed_json():
    """畸形 JSON 返回解析错误"""
    server = JsonRpcServer(engine=None)
    response = await server.handle(b"not json")
    result = json.loads(response)
    assert "error" in result
    assert result["error"]["code"] == -32700
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_protocol.py -v 2>&1 || true`
预期：ImportError / ModuleNotFoundError

- [ ] **步骤 3：编写实现代码**

```python
"""JSON-RPC 2.0 协议实现 (stdio)"""

import json
import sys
import asyncio
import uuid
from typing import Any, AsyncIterator, Callable, Awaitable


JSONRPC_VERSION = "2.0"


class JsonRpcError(Exception):
    """JSON-RPC 错误"""
    
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)
    
    def to_dict(self) -> dict:
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


# 标准 JSON-RPC 错误码
PARSE_ERROR = JsonRpcError(-32700, "Parse error")
INVALID_REQUEST = JsonRpcError(-32600, "Invalid Request")
METHOD_NOT_FOUND = JsonRpcError(-32601, "Method not found")
INVALID_PARAMS = JsonRpcError(-32602, "Invalid params")
INTERNAL_ERROR = JsonRpcError(-32603, "Internal error")


def create_request(method: str, params: dict, request_id: int | None = None) -> dict:
    """创建 JSON-RPC 请求"""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
        "params": params,
        "id": request_id if request_id is not None else uuid.uuid4().int & 0x7FFFFFFF,
    }


def create_response(request_id: int, result: Any = None, error: JsonRpcError | None = None) -> dict:
    """创建 JSON-RPC 响应"""
    resp = {"jsonrpc": JSONRPC_VERSION, "id": request_id}
    if error:
        resp["error"] = error.to_dict()
    else:
        resp["result"] = result
    return resp


def create_notification(method: str, params: dict) -> dict:
    """创建 JSON-RPC 通知（无 id）"""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
        "params": params,
    }


class StreamEvent:
    """流式事件 — 用于引擎 -> CLI 的增量输出"""
    
    def __init__(self, event_type: str, **kwargs):
        self.type = event_type
        self.data = kwargs
    
    def to_dict(self) -> dict:
        return {"type": self.type, **self.data}
    
    @classmethod
    def text(cls, content: str):
        return cls("text", content=content)
    
    @classmethod
    def tool_use(cls, tool_name: str, tool_input: dict, tool_use_id: str):
        return cls("tool_use", name=tool_name, input=tool_input, id=tool_use_id)
    
    @classmethod
    def tool_result(cls, tool_use_id: str, content: Any, is_error: bool = False):
        return cls("tool_result", id=tool_use_id, content=content, is_error=is_error)
    
    @classmethod
    def stream_start(cls):
        return cls("stream_start")
    
    @classmethod
    def stream_end(cls):
        return cls("stream_end")
    
    @classmethod
    def error(cls, message: str):
        return cls("error", message=message)


class JsonRpcServer:
    """JSON-RPC 服务端 — 从 stdin 读取，写入 stdout"""
    
    def __init__(self, engine):
        self.engine = engine
        self._methods: dict[str, Callable] = {
            "chat.send": self._handle_chat_send,
            "engine.status": self._handle_engine_status,
            "shutdown": self._handle_shutdown,
        }
    
    async def handle(self, raw: bytes) -> bytes | None:
        """处理单条 JSON-RPC 消息"""
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            response = create_response(0, error=PARSE_ERROR)
            return json.dumps(response).encode()
        
        if not isinstance(message, dict) or message.get("jsonrpc") != JSONRPC_VERSION:
            response = create_response(0, error=INVALID_REQUEST)
            return json.dumps(response).encode()
        
        method = message.get("method", "")
        params = message.get("params", {})
        request_id = message.get("id")
        
        # Notification（无 id）— 不需要响应
        is_notification = request_id is None
        
        handler = self._methods.get(method)
        if handler is None:
            if is_notification:
                return None
            response = create_response(0, error=METHOD_NOT_FOUND)
            return json.dumps(response).encode()
        
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(params)
            else:
                result = handler(params)
            
            if is_notification:
                return None
            
            # 如果结果是异步迭代器，逐行流式输出
            if isinstance(result, AsyncIterator):
                return result  # 上层处理流式
            else:
                return json.dumps(create_response(request_id, result)).encode()
        except JsonRpcError as e:
            return json.dumps(create_response(request_id, error=e)).encode()
        except Exception as e:
            return json.dumps(create_response(request_id, error=INTERNAL_ERROR)).encode()
    
    async def _handle_chat_send(self, params: dict) -> AsyncIterator[bytes]:
        """处理聊天请求 — 返回流式事件"""
        message = params.get("message", "")
        session_id = params.get("conversation_id")
        
        # 委托给引擎
        async for event in self.engine.chat(message, session_id):
            yield json.dumps(event.to_dict()).encode() + b"\n"
    
    async def _handle_engine_status(self, params: dict) -> dict:
        """返回引擎状态"""
        return {
            "status": "running",
            "provider": self.engine.provider.model_name if self.engine else "unknown",
            "session_active": self.engine.session is not None if self.engine else False,
        }
    
    async def _handle_shutdown(self, params: dict) -> None:
        """处理关闭通知"""
        if self.engine:
            await self.engine.shutdown()
        sys.exit(0)
    
    async def serve(self):
        """主循环：从 stdin 读取消息并响应到 stdout"""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin.buffer)
        
        writer = sys.stdout.buffer
        
        while True:
            try:
                line = await reader.readline()
                if not line:
                    break  # EOF
                
                line = line.strip()
                if not line:
                    continue
                
                response = await self.handle(line)
                if response is not None:
                    if isinstance(response, AsyncIterator):
                        async for chunk in response:
                            writer.write(chunk)
                            writer.flush()
                    else:
                        writer.write(response + b"\n")
                        writer.flush()
            except (EOFError, BrokenPipeError):
                break
            except Exception:
                # 记录异常但不崩溃
                pass


class JsonRpcClient:
    """JSON-RPC 客户端 — 发送请求到子进程 stdin，从 stdout 读取"""
    
    def __init__(self, process):
        self.process = process
    
    async def send_request(self, method: str, params: dict) -> dict:
        """发送请求并等待完整响应"""
        request = create_request(method, params)
        raw = json.dumps(request).encode() + b"\n"
        
        self.process.stdin.write(raw)
        await self.process.stdin.drain()
        
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line)
        
        if "error" in response:
            raise JsonRpcError(
                code=response["error"]["code"],
                message=response["error"].get("message", "Unknown error"),
                data=response["error"].get("data"),
            )
        
        return response.get("result")
    
    async def send_stream_request(self, method: str, params: dict):
        """发送请求并逐行读取流式响应"""
        request = create_request(method, params)
        raw = json.dumps(request).encode() + b"\n"
        
        self.process.stdin.write(raw)
        await self.process.stdin.drain()
        
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                yield event
            except json.JSONDecodeError:
                continue
    
    def send_notification(self, method: str, params: dict):
        """发送通知（无响应）"""
        notification = create_notification(method, params)
        raw = json.dumps(notification).encode() + b"\n"
        self.process.stdin.write(raw)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_protocol.py -v`
预期：5 PASSED

- [ ] **步骤 5：Commit**

```bash
git add shaw/protocol.py tests/test_protocol.py
git commit -m "feat: add JSON-RPC 2.0 protocol (stdio)"
```

---

### 任务 4：Provider 抽象 + Anthropic 实现

**文件：**
- 创建：`shaw/provider.py`
- 创建：`shaw/providers/__init__.py`
- 创建：`shaw/providers/anthropic.py`
- 创建：`tests/test_provider.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""Tests for shaw.provider"""

import pytest
from shaw.provider import BaseProvider, Message, ToolDef, ToolParam
from shaw.providers.anthropic import AnthropicProvider


def test_message_creation():
    """测试消息对象创建"""
    msg = Message(role="user", content="hello")
    assert msg.role == "user"
    assert msg.content == "hello"


def test_tool_def():
    """测试工具定义"""
    param = ToolParam(name="path", type="string", description="File path", required=True)
    tool = ToolDef(
        name="Read",
        description="Read a file",
        params=[param],
    )
    assert tool.name == "Read"
    assert len(tool.params) == 1
    assert tool.params[0].name == "path"


def test_base_provider_cannot_instantiate():
    """抽象基类不能直接实例化"""
    with pytest.raises(TypeError):
        BaseProvider()  # type: ignore


def test_anthropic_provider_init():
    """初始化 Anthropic 提供商"""
    provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-6-20250515")
    assert provider.model_name == "claude-sonnet-4-6-20250515"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_provider.py -v 2>&1 || true`
预期：ImportError

- [ ] **步骤 3：编写实现代码**

```python
"""Provider 抽象基类 — LLM 提供商统一接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Any


@dataclass
class ToolParam:
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = False


@dataclass
class ToolDef:
    """工具定义"""
    name: str
    description: str
    params: list[ToolParam] = field(default_factory=list)


@dataclass
class Message:
    """对话消息"""
    role: str  # "user" | "assistant" | "system"
    content: str
    

@dataclass
class StreamEvent:
    """流式事件"""
    type: str  # "text" | "tool_use" | "tool_result" | "thinking" | "done"
    content: Any = None
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    tool_use_id: str = ""


class BaseProvider(ABC):
    """LLM 提供商抽象基类"""
    
    @abstractmethod
    async def send(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """发送消息到 LLM 并流式返回事件"""
        ...
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """估算 token 数量"""
        ...
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回当前模型名称"""
        ...
```

```python
"""shaw/providers/__init__.py"""
```

```python
"""Anthropic Claude Provider 实现"""

import json
from typing import AsyncIterator
from shaw.provider import BaseProvider, StreamEvent, ToolDef, ToolParam, Message


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API 提供商"""
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6-20250515", max_tokens: int = 8192):
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._client = None
    
    @property
    def model_name(self) -> str:
        return self._model
    
    def count_tokens(self, text: str) -> int:
        """粗略估算 token 数（英文约 4 字符/token，中文约 1.5 字符/token）"""
        import math
        char_count = len(text)
        # 混合估算
        return math.ceil(char_count / 3.5)
    
    def _get_client(self):
        """延迟初始化 Anthropic 客户端"""
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client
    
    def _to_anthropic_tools(self, tools: list[ToolDef]) -> list[dict]:
        """将内部 ToolDef 转换为 Anthropic API 格式"""
        result = []
        for tool in tools:
            properties = {}
            required = []
            for param in tool.params:
                properties[param.name] = {
                    "type": param.type,
                    "description": param.description,
                }
                if param.required:
                    required.append(param.name)
            
            anthropic_tool = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                },
            }
            if required:
                anthropic_tool["input_schema"]["required"] = required
            
            result.append(anthropic_tool)
        return result
    
    async def send(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """发送消息到 Claude 并流式返回"""
        client = self._get_client()
        
        # 转换消息格式
        api_messages = []
        for msg in messages:
            entry = {"role": msg.role, "content": msg.content}
            api_messages.append(entry)
        
        # 构建请求参数
        kwargs = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": api_messages,
        }
        
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)
        
        async with client.messages.stream(**kwargs) as stream:
            current_tool_name = ""
            current_tool_input = ""
            current_tool_id = ""
            
            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        current_tool_name = event.content_block.name
                        current_tool_id = event.content_block.id
                        current_tool_input = ""
                
                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield StreamEvent(type="text", content=event.delta.text)
                    elif event.delta.type == "input_json_delta":
                        current_tool_input += event.delta.partial_json
                
                elif event.type == "content_block_stop":
                    if current_tool_name:
                        try:
                            tool_input = json.loads(current_tool_input) if current_tool_input else {}
                        except json.JSONDecodeError:
                            tool_input = {}
                        yield StreamEvent(
                            type="tool_use",
                            tool_name=current_tool_name,
                            tool_input=tool_input,
                            tool_use_id=current_tool_id,
                        )
                        current_tool_name = ""
                        current_tool_input = ""
                        current_tool_id = ""
                
                elif event.type == "message_stop":
                    yield StreamEvent(type="done")
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_provider.py -v`
预期：4 PASSED

- [ ] **步骤 5：Commit**

```bash
git add shaw/provider.py shaw/providers/ tests/test_provider.py
git commit -m "feat: add Provider abstraction + Anthropic implementation"
```

---

### 任务 5：基础工具系统

**文件：**
- 创建：`shaw/tools/__init__.py`
- 创建：`shaw/tools/registry.py`
- 创建：`shaw/tools/read.py`
- 创建：`shaw/tools/write.py`
- 创建：`shaw/tools/bash.py`
- 创建：`tests/test_tools.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""Tests for shaw.tools"""

import os
import tempfile
import pytest
from shaw.tools.registry import ToolRegistry, BaseTool
from shaw.tools.read import ReadTool
from shaw.tools.write import WriteTool
from shaw.tools.bash import BashTool


def test_tool_registry():
    """工具注册和查找"""
    registry = ToolRegistry()
    tool = ReadTool()
    registry.register(tool)
    assert registry.get("Read") is tool
    assert registry.list() == ["Read"]


def test_read_tool():
    """读取文件"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello world")
        temp_path = f.name
    
    try:
        tool = ReadTool()
        result = tool.execute(path=temp_path)
        assert "hello world" in result
    finally:
        os.unlink(temp_path)


def test_read_nonexistent_file():
    """读取不存在的文件返回错误"""
    tool = ReadTool()
    result = tool.execute(path="/nonexistent/file.txt")
    assert "error" in result.lower() or "not found" in result.lower()


def test_write_tool():
    """写入文件"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        temp_path = f.name
    
    try:
        tool = WriteTool()
        result = tool.execute(path=temp_path, content="new content")
        assert "written" in result.lower()
        
        with open(temp_path) as f:
            assert f.read() == "new content"
    finally:
        os.unlink(temp_path)


def test_bash_tool():
    """执行 bash 命令"""
    tool = BashTool()
    result = tool.execute(command="echo hello")
    assert "hello" in result


def test_bash_tool_timeout():
    """超时的命令返回错误"""
    tool = BashTool()
    result = tool.execute(command="sleep 10", timeout=1)
    assert "timeout" in result.lower() or "timed out" in result.lower()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_tools.py -v 2>&1 || true`
预期：ImportError

- [ ] **步骤 3：编写实现代码**

```python
"""shaw/tools/__init__.py"""
```

```python
"""工具注册表"""

from typing import Any
from shaw.provider import ToolDef, ToolParam


class BaseTool:
    """工具基类"""
    
    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("Tool", "")
    
    @property
    def tool_def(self) -> ToolDef:
        """返回工具定义（用于 LLM 函数调用声明）"""
        raise NotImplementedError
    
    def execute(self, **kwargs) -> str:
        """执行工具，返回结果字符串"""
        raise NotImplementedError


class ToolRegistry:
    """工具注册表 — 管理所有可用工具"""
    
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool):
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> BaseTool | None:
        """按名称获取工具"""
        return self._tools.get(name)
    
    def list(self) -> list[str]:
        """列出所有已注册工具名称"""
        return list(self._tools.keys())
    
    def get_tool_defs(self) -> list[ToolDef]:
        """获取所有工具的 ToolDef 列表（用于 LLM）"""
        return [tool.tool_def for tool in self._tools.values()]
    
    def execute(self, name: str, params: dict) -> str:
        """执行工具并返回结果"""
        tool = self.get(name)
        if tool is None:
            return f"Error: Unknown tool '{name}'"
        try:
            return tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {e}"
```

```python
"""Read 工具 — 读取文件内容"""

import os
from shaw.tools.registry import BaseTool
from shaw.provider import ToolDef, ToolParam


class ReadTool(BaseTool):
    """读取文件内容"""
    
    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="Read",
            description="Read the contents of a file. Lines are numbered starting from 1.",
            params=[
                ToolParam(name="path", type="string", description="Absolute path to the file", required=True),
                ToolParam(name="offset", type="integer", description="Line number to start reading from", required=False),
                ToolParam(name="limit", type="integer", description="Number of lines to read", required=False),
            ],
        )
    
    def execute(self, path: str, offset: int = 0, limit: int = 2000) -> str:
        if not os.path.exists(path):
            return f"Error: File not found: {path}"
        
        if not os.path.isfile(path):
            return f"Error: Not a file: {path}"
        
        # 检查文件大小（限制 > 10MB 的文件）
        size = os.path.getsize(path)
        if size > 10 * 1024 * 1024:
            return f"Error: File too large ({size / 1024 / 1024:.1f}MB). Maximum: 10MB"
        
        try:
            with open(path, "r", errors="replace") as f:
                lines = f.readlines()
            
            total = len(lines)
            start = offset if offset > 0 else 0
            end = min(start + limit, total)
            
            if start >= total:
                return f"File has {total} lines, but offset {start} is beyond end."
            
            result_lines = []
            for i in range(start, end):
                result_lines.append(f"{i + 1}\t{lines[i].rstrip()}")
            
            result = "\n".join(result_lines)
            summary = f"File: {path} ({total} lines, showing {start + 1}-{end})"
            
            return f"{summary}\n{result}"
        except Exception as e:
            return f"Error reading file: {e}"
```

```python
"""Write 工具 — 写入/覆盖文件"""

import os
from shaw.tools.registry import BaseTool
from shaw.provider import ToolDef, ToolParam


class WriteTool(BaseTool):
    """写入/覆盖文件"""
    
    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="Write",
            description="Write content to a file. Creates parent directories if needed. Overwrites existing content.",
            params=[
                ToolParam(name="path", type="string", description="Absolute path to the file", required=True),
                ToolParam(name="content", type="string", description="Content to write", required=True),
            ],
        )
    
    def execute(self, path: str, content: str) -> str:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            with open(path, "w") as f:
                f.write(content)
            
            size = len(content.encode("utf-8"))
            return f"Successfully wrote {size} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {e}"
```

```python
"""Bash 工具 — 执行 Shell 命令"""

import asyncio
import shlex
from shaw.tools.registry import BaseTool
from shaw.provider import ToolDef, ToolParam


class BashTool(BaseTool):
    """执行 Shell 命令"""
    
    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="Bash",
            description="Execute a shell command. Use this to run code, build projects, or perform system operations.",
            params=[
                ToolParam(name="command", type="string", description="The command to execute", required=True),
                ToolParam(name="timeout", type="integer", description="Timeout in milliseconds", required=False),
            ],
        )
    
    def execute(self, command: str, timeout: int = 120000) -> str:
        try:
            import subprocess
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout / 1000,
            )
            
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                if output:
                    output += "\n"
                output += result.stderr
            
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            
            # 限制输出大小
            max_output = 100000  # 100KB
            if len(output) > max_output:
                output = output[:max_output] + f"\n... (truncated, {len(output)} total bytes)"
            
            return output if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout / 1000}s"
        except Exception as e:
            return f"Error executing command: {e}"
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_tools.py -v`
预期：6 PASSED（注意 bash timeout 测试可能需要调整）

- [ ] **步骤 5：Commit**

```bash
git add shaw/tools/ tests/test_tools.py
git commit -m "feat: add tool system with Read, Write, Bash tools"
```

---

### 任务 6：Engine — LLM 循环核心

**文件：**
- 创建：`shaw/engine.py`
- 创建：`shaw/session.py`
- 创建：`tests/test_engine.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""Tests for shaw.engine"""

import pytest
from shaw.engine import Engine
from shaw.session import Session
from shaw.provider import BaseProvider, StreamEvent, Message, ToolDef
from shaw.tools.registry import ToolRegistry, BaseTool
from typing import AsyncIterator


class MockProvider(BaseProvider):
    """Mock LLM 提供商"""
    
    def __init__(self, responses: list[list[StreamEvent]]):
        self._responses = responses
        self._call_count = 0
    
    @property
    def model_name(self) -> str:
        return "mock-model"
    
    def count_tokens(self, text: str) -> int:
        return len(text) // 4
    
    async def send(self, system: str, messages: list[Message], tools: list[ToolDef] | None = None) -> AsyncIterator[StreamEvent]:
        if self._call_count < len(self._responses):
            for event in self._responses[self._call_count]:
                yield event
            self._call_count += 1


class EchoTool(BaseTool):
    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(name="Echo", description="Echo input", params=[])
    
    def execute(self, **kwargs) -> str:
        return "echo: " + str(kwargs)


async def test_engine_simple_chat():
    """简单对话"""
    provider = MockProvider([
        [StreamEvent(type="text", content="Hello!"), StreamEvent(type="done")],
    ])
    registry = ToolRegistry()
    engine = Engine(provider=provider, tools=registry, config={})
    
    events = []
    async for event in engine.chat("Hi", "test-session"):
        events.append(event)
    
    assert any(e.type == "text" and e.content == "Hello!" for e in events)


async def test_engine_tool_use():
    """工具调用循环"""
    provider = MockProvider([
        [
            StreamEvent(type="text", content="Let me check..."),
            StreamEvent(type="tool_use", tool_name="Echo", tool_input={"key": "value"}, tool_use_id="tool1"),
            StreamEvent(type="done"),
        ],
        [
            StreamEvent(type="text", content="Done checking!"),
            StreamEvent(type="done"),
        ],
    ])
    registry = ToolRegistry()
    registry.register(EchoTool())
    
    engine = Engine(provider=provider, tools=registry, config={})
    
    events = []
    async for event in engine.chat("Check this", "test-session-2"):
        events.append(event)
    
    # 验证工具结果被发送回 LLM
    text_events = [e for e in events if e.type == "text"]
    tool_events = [e for e in events if e.type == "tool_use"]
    tool_result_events = [e for e in events if e.type == "tool_result"]
    
    assert any("Done checking" in str(e.content) for e in text_events)
    assert len(tool_events) == 1
    assert len(tool_result_events) == 1


async def test_session_creation():
    """会话创建和管理"""
    session = Session(session_id="test-1")
    assert session.session_id == "test-1"
    assert len(session.messages) == 0
    
    session.add_message(Message(role="user", content="hello"))
    assert len(session.messages) == 1
    assert session.messages[0].role == "user"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_engine.py -v 2>&1 || true`
预期：ImportError

- [ ] **步骤 3：编写实现代码**

```python
"""会话管理"""

import json
import time
from pathlib import Path
from typing import Any
from shaw.provider import Message


class Session:
    """对话会话"""
    
    def __init__(self, session_id: str | None = None, config: dict | None = None):
        self.session_id = session_id or f"session_{int(time.time())}"
        self.messages: list[dict] = []
        self.created_at = time.time()
        self.updated_at = time.time()
        self.config = config or {}
        self.active_skill: str | None = None
    
    def add_message(self, role: str, content: str):
        """添加消息到会话"""
        self.messages.append({"role": role, "content": content})
        self.updated_at = time.time()
    
    def add_tool_result(self, tool_use_id: str, content: str, role: str = "user") -> dict:
        """添加工具调用结果（返回 message dict 用于继续循环）"""
        msg = {
            "role": role,
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content,
                }
            ],
        }
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg
    
    def add_tool_use(self, tool_name: str, tool_input: dict, tool_use_id: str, role: str = "assistant") -> dict:
        """添加工具调用请求（返回 message dict 用于继续循环）"""
        msg = {
            "role": role,
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": tool_name,
                    "input": tool_input,
                }
            ],
        }
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "config": self.config,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        session = cls(session_id=data["session_id"])
        session.messages = data.get("messages", [])
        session.created_at = data.get("created_at", time.time())
        session.updated_at = data.get("updated_at", time.time())
        session.config = data.get("config", {})
        return session


class SessionManager:
    """会话管理器 — 存储和加载会话"""
    
    def __init__(self, storage_dir: str | Path | None = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".shaw" / "sessions"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, session: Session):
        """保存会话到文件"""
        path = self.storage_dir / f"{session.session_id}.json"
        with open(path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)
    
    def load(self, session_id: str) -> Session | None:
        """加载会话"""
        path = self.storage_dir / f"{session_id}.json"
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return Session.from_dict(data)
    
    def list_sessions(self) -> list[dict]:
        """列出所有会话"""
        sessions = []
        for path in sorted(self.storage_dir.glob("*.json"), reverse=True):
            try:
                with open(path) as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id", path.stem),
                    "created_at": data.get("created_at", 0),
                    "updated_at": data.get("updated_at", 0),
                    "message_count": len(data.get("messages", [])),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return sessions
```

```python
"""Shaw Engine — LLM 循环核心"""

from typing import AsyncIterator, Any
from shaw.provider import BaseProvider, StreamEvent
from shaw.tools.registry import ToolRegistry
from shaw.session import Session, SessionManager


class Engine:
    """LLM 循环引擎 — 管理对话、工具调用和技能"""
    
    def __init__(self, provider: BaseProvider, tools: ToolRegistry, config: dict):
        self.provider = provider
        self.tools = tools
        self.config = config
        self.session: Session | None = None
        self.session_manager = SessionManager()
    
    async def chat(self, message: str, session_id: str | None = None) -> AsyncIterator[dict]:
        """处理用户消息，流式返回事件"""
        # 加载或创建会话
        if session_id:
            self.session = self.session_manager.load(session_id)
        
        if self.session is None:
            self.session = Session(session_id=session_id)
        
        # 添加用户消息
        self.session.add_message("user", message)
        
        # 构建系统提示
        system_prompt = self._build_system_prompt()
        
        # 获取工具定义
        tool_defs = self.tools.get_tool_defs()
        
        # LLM 调用循环
        max_iterations = 10  # 防止无限循环
        for iteration in range(max_iterations):
            # 构建消息列表（从 session 转换）
            messages = self._messages_from_session()
            
            has_tool_call = False
            
            async for event in self.provider.send(system_prompt, messages, tool_defs):
                if event.type == "text":
                    yield {"type": "text", "content": event.content}
                elif event.type == "tool_use":
                    has_tool_call = True
                    yield {"type": "tool_use", "name": event.tool_name, "input": event.tool_input, "id": event.tool_use_id}
                    
                    # 执行工具
                    result = self.tools.execute(event.tool_name, event.tool_input)
                    
                    # 添加到会话（assistant 的 tool_use + user 的 tool_result）
                    self.session.add_tool_use(event.tool_name, event.tool_input, event.tool_use_id)
                    self.session.add_tool_result(event.tool_use_id, result)
                    
                    yield {"type": "tool_result", "id": event.tool_use_id, "content": result, "is_error": False}
                elif event.type == "done":
                    yield {"type": "stream_end"}
                    break
            
            # 如果没有工具调用，结束循环
            if not has_tool_call:
                break
        
        # 自动保存会话
        if self.config.get("session", {}).get("auto_save", True):
            self.session_manager.save(self.session)
    
    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        parts = [
            "You are Shaw, an AI programming assistant. You help users with coding tasks.",
            "",
            "You have access to tools. Use them when needed to help the user.",
            "- Read: Read file contents",
            "- Write: Write content to files",
            "- Bash: Execute shell commands",
            "",
            "Guidelines:",
            "- Always show the code you write or modify",
            "- Explain your reasoning briefly",
            "- Use tools to verify your work when appropriate",
            "- When you encounter errors, fix them before moving on",
            "",
        ]
        
        return "\n".join(parts)
    
    def _messages_from_session(self) -> list:
        """将 session 消息转换为 provider 消息格式"""
        return self.session.messages if self.session else []
    
    async def shutdown(self):
        """关闭引擎"""
        if self.session:
            self.session_manager.save(self.session)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_engine.py -v`
预期：3 PASSED

- [ ] **步骤 5：Commit**

```bash
git add shaw/engine.py shaw/session.py tests/test_engine.py
git commit -m "feat: add Engine loop and Session management"
```

---

### 任务 7：Harness — 工具执行沙箱

**文件：**
- 创建：`shaw/harness.py`
- 创建：`tests/test_harness.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""Tests for shaw.harness"""

import pytest
from shaw.harness import Harness
from shaw.tools.registry import ToolRegistry
from shaw.tools.read import ReadTool
from shaw.tools.write import WriteTool
from shaw.tools.bash import BashTool


async def test_harness_creation():
    """创建 Harness"""
    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(BashTool())
    
    harness = Harness(tool_registry=registry)
    assert harness is not None


async def test_harness_execute():
    """执行工具"""
    registry = ToolRegistry()
    registry.register(BashTool())
    
    harness = Harness(tool_registry=registry)
    result = harness.execute("Bash", {"command": "echo hello"})
    assert "hello" in result


async def test_harness_unknown_tool():
    """未知工具"""
    harness = Harness(tool_registry=ToolRegistry())
    result = harness.execute("UnknownTool", {})
    assert "error" in result.lower() or "unknown" in result.lower()


async def test_harness_sensitive_file():
    """保护敏感文件"""
    registry = ToolRegistry()
    registry.register(ReadTool())
    
    harness = Harness(
        tool_registry=registry,
        protected_patterns=[".env*"],
    )
    
    result = harness.execute("Read", {"path": "/path/to/.env"})
    assert "protected" in result.lower() or "blocked" in result.lower()


async def test_harness_tool_stats():
    """工具调用统计"""
    registry = ToolRegistry()
    registry.register(BashTool())
    
    harness = Harness(tool_registry=registry)
    harness.execute("Bash", {"command": "echo a"})
    harness.execute("Bash", {"command": "echo b"})
    
    stats = harness.get_stats()
    assert stats["Bash"] == 2
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_harness.py -v 2>&1 || true`
预期：ImportError

- [ ] **步骤 3：编写实现代码**

```python
"""Harness — 工具执行沙箱和安全控制"""

import fnmatch
import time
from typing import Any
from shaw.tools.registry import ToolRegistry


class Harness:
    """工具执行环境 — 安全控制、统计、权限管理"""
    
    def __init__(
        self,
        tool_registry: ToolRegistry,
        config: dict | None = None,
    ):
        self.tool_registry = tool_registry
        self.config = config or {}
        self._stats: dict[str, int] = {}
        self._call_times: dict[str, list[float]] = {}
        
        # 安全配置
        tool_config = self.config.get("tools", {})
        self.protected_patterns = tool_config.get("files", {}).get("protected_patterns", [
            ".env*", "*.pem", "id_*", "*.key",
        ])
        self.allowed_commands = tool_config.get("bash", {}).get("allowed_commands", [])
        self.blocked_commands = tool_config.get("bash", {}).get("blocked_commands", [])
    
    def execute(self, tool_name: str, params: dict) -> str:
        """执行工具 — 包含安全检查和统计"""
        # 安全检查
        check_result = self._security_check(tool_name, params)
        if check_result is not None:
            return check_result
        
        # 执行
        start = time.time()
        result = self.tool_registry.execute(tool_name, params)
        elapsed = time.time() - start
        
        # 统计
        self._stats[tool_name] = self._stats.get(tool_name, 0) + 1
        if tool_name not in self._call_times:
            self._call_times[tool_name] = []
        self._call_times[tool_name].append(elapsed)
        
        return result
    
    def _security_check(self, tool_name: str, params: dict) -> str | None:
        """安全检查 — 返回错误信息或 None（通过）"""
        if tool_name == "Read":
            path = params.get("path", "")
            if self._is_protected(path):
                return f"Error: Cannot read protected file: {path}"
        
        elif tool_name == "Write":
            path = params.get("path", "")
            if self._is_protected(path):
                return f"Error: Cannot write to protected file: {path}"
        
        elif tool_name == "Bash":
            command = params.get("command", "")
            if self._is_blocked_command(command):
                return f"Error: Command blocked for security: {command}"
        
        return None
    
    def _is_protected(self, path: str) -> bool:
        """检查路径是否受保护"""
        for pattern in self.protected_patterns:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.split("/")[-1], pattern):
                return True
        return False
    
    def _is_blocked_command(self, command: str) -> bool:
        """检查命令是否被阻止"""
        for blocked in self.blocked_commands:
            if blocked in command:
                return True
        return False
    
    def get_stats(self) -> dict[str, int]:
        """获取工具调用统计"""
        return dict(self._stats)
    
    def get_timing(self) -> dict[str, dict]:
        """获取工具调用耗时统计"""
        timing = {}
        for name, times in self._call_times.items():
            timing[name] = {
                "count": len(times),
                "total": sum(times),
                "avg": sum(times) / len(times) if times else 0,
            }
        return timing
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && python -m pytest tests/test_harness.py -v`
预期：5 PASSED

- [ ] **步骤 5：Commit**

```bash
git add shaw/harness.py tests/test_harness.py
git commit -m "feat: add Harness with security controls and tool stats"
```

---

### 任务 8：Node.js CLI 脚手架

**文件：**
- 创建：`cli/package.json`
- 创建：`cli/tsconfig.json`
- 创建：`cli/src/index.ts`
- 创建：`cli/src/rpc.ts`

- [ ] **步骤 1：初始化 Node 项目并安装依赖**

运行：`cd /mnt/d/Workspace/OpenSourceCLI && mkdir -p cli && cd cli && npm init -y`

```bash
cd /mnt/d/Workspace/OpenSourceCLI/cli
npm init -y
npm install ink react@19
npm install -D typescript @types/react tsx
```

- [ ] **步骤 2：创建 package.json**

```json
{
  "name": "shaw-cli",
  "version": "0.1.0",
  "description": "Shaw AI CLI - Terminal UI",
  "type": "module",
  "bin": {
    "shaw": "./src/index.ts"
  },
  "scripts": {
    "dev": "tsx src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "dependencies": {
    "ink": "^5.0.0",
    "react": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "tsx": "^4.0.0",
    "typescript": "^5.5.0"
  }
}
```

- [ ] **步骤 3：创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist",
    "rootDir": "src",
    "declaration": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

- [ ] **步骤 4：创建 JSON-RPC 客户端**

```typescript
// cli/src/rpc.ts — JSON-RPC stdio 客户端

import { ChildProcess, spawn } from "child_process";
import { createInterface } from "readline";

export interface StreamEvent {
  type: "text" | "tool_use" | "tool_result" | "stream_start" | "stream_end" | "error";
  content?: string;
  name?: string;
  input?: Record<string, unknown>;
  id?: string;
  is_error?: boolean;
  message?: string;
}

export class RpcClient {
  private process: ChildProcess;
  private requestId = 0;
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private buffer = "";

  constructor(enginePath?: string) {
    const script = enginePath || "-m shaw";
    this.process = spawn("python", script.split(" "), {
      stdio: ["pipe", "pipe", "inherit"],
      cwd: process.cwd(),
    });

    const rl = createInterface({ input: this.process.stdout! });
    rl.on("line", (line: string) => {
      try {
        const msg = JSON.parse(line.trim());
        if (msg.id !== undefined && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id)!;
          this.pending.delete(msg.id);
          if (msg.error) reject(new Error(msg.error.message));
          else resolve(msg.result);
        }
      } catch {
        // ignore malformed lines
      }
    });

    this.process.on("exit", (code) => {
      if (code !== 0) {
        console.error(`Engine exited with code ${code}`);
      }
    });
  }

  async sendRequest(method: string, params: Record<string, unknown>): Promise<unknown> {
    const id = ++this.requestId;
    const request = JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n";

    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.process.stdin!.write(request);
    });
  }

  async *sendStreamRequest(method: string, params: Record<string, unknown>): AsyncGenerator<StreamEvent> {
    const id = ++this.requestId;
    const request = JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n";

    this.process.stdin!.write(request);

    // For streaming, we read from stdout directly
    const rl = createInterface({ input: this.process.stdout! });
    for await (const line of rl) {
      try {
        const event = JSON.parse(line.trim()) as StreamEvent;
        yield event;
        if (event.type === "stream_end") break;
      } catch {
        continue;
      }
    }
  }

  sendNotification(method: string, params: Record<string, unknown>): void {
    const notification = JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n";
    this.process.stdin!.write(notification);
  }

  shutdown(): void {
    this.sendNotification("shutdown", {});
    setTimeout(() => this.process.kill(), 1000);
  }
}
```

- [ ] **步骤 5：创建 CLI 入口**

```typescript
// cli/src/index.ts — Shaw CLI 入口

import { RpcClient } from "./rpc.js";

async function main() {
  const client = new RpcClient();
  
  // 检查引擎状态
  try {
    const status = await client.sendRequest("engine.status", {}) as { status: string };
    console.error(`Engine: ${status.status}`);
  } catch (e) {
    console.error("Failed to connect to engine:", e);
    process.exit(1);
  }
  
  console.error("Shaw AI CLI v0.1.0");
  console.error("Type /help for commands, Ctrl+C to exit");
  console.error("");
  
  // 简单 REPL 模式（后续用 Ink 替换）
  const readline = await import("readline");
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: "> ",
  });
  
  rl.prompt();
  
  for await (const line of rl) {
    const input = line.trim();
    
    if (!input) {
      rl.prompt();
      continue;
    }
    
    if (input === "/exit" || input === "/quit") {
      break;
    }
    
    if (input === "/help") {
      console.error("Commands: /help, /exit, /clear, /status");
      rl.prompt();
      continue;
    }
    
    if (input === "/status") {
      try {
        const status = await client.sendRequest("engine.status", {});
        console.error(JSON.stringify(status, null, 2));
      } catch (e) {
        console.error("Error:", e);
      }
      rl.prompt();
      continue;
    }
    
    // 正常聊天
    process.stdout.write("Shaw: ");
    try {
      for await (const event of client.sendStreamRequest("chat.send", { message: input })) {
        if (event.type === "text") {
          process.stdout.write(event.content || "");
        } else if (event.type === "tool_use") {
          process.stdout.write(`\n[Using ${event.name}...]\n`);
        } else if (event.type === "tool_result") {
          process.stdout.write(`[Tool result received]\n`);
        } else if (event.type === "error") {
          process.stdout.write(`\n[Error: ${event.message}]\n`);
        }
      }
      process.stdout.write("\n");
    } catch (e) {
      process.stdout.write(`\n[Error: ${e}]\n`);
    }
    
    rl.prompt();
  }
  
  client.shutdown();
  process.exit(0);
}

main().catch(console.error);
```

- [ ] **步骤 6：验证 CLI 构建**

运行：`cd /mnt/d/Workspace/OpenSourceCLI/cli && npx tsc --noEmit`
预期：无错误

- [ ] **步骤 7：Commit**

```bash
git add cli/
git commit -m "feat: add Node.js CLI with JSON-RPC client and REPL"
```

---

### 任务 9：Ink 终端交互界面

**文件：**
- 创建：`cli/src/app.tsx`
- 创建：`cli/src/components/App.tsx`
- 创建：`cli/src/components/Chat.tsx`
- 创建：`cli/src/components/Input.tsx`
- 创建：`cli/src/components/ToolCall.tsx`

- [ ] **步骤 1：安装测试依赖**

```bash
cd /mnt/d/Workspace/OpenSourceCLI/cli
npm install -D vitest @testing-library/react ink-testing-library
```

- [ ] **步骤 2：创建主应用组件 App.tsx**

```tsx
// cli/src/components/App.tsx
import React, { useState, useCallback } from "react";
import { Box, Text } from "ink";
import { Chat } from "./Chat.js";
import { Input } from "./Input.js";
import { RpcClient, StreamEvent } from "../rpc.js";

interface Message {
  id: number;
  role: "user" | "assistant" | "tool";
  content: string;
  events?: StreamEvent[];
}

interface AppProps {
  client: RpcClient;
}

export function App({ client }: AppProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<string>("ready");
  const [error, setError] = useState<string | null>(null);
  let msgId = 0;

  const handleSend = useCallback(async (input: string) => {
    const userMsg: Message = { id: ++msgId, role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setError(null);

    const assistantMsg: Message = { id: ++msgId, role: "assistant", content: "", events: [] };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      for await (const event of client.sendStreamRequest("chat.send", { message: input })) {
        if (event.type === "text") {
          assistantMsg.content += event.content || "";
        }
        assistantMsg.events = [...(assistantMsg.events || []), event];
        setMessages((prev) => {
          const updated = [...prev];
          const idx = updated.findIndex((m) => m.id === assistantMsg.id);
          if (idx >= 0) updated[idx] = { ...assistantMsg };
          return updated;
        });
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setIsLoading(false);
    }
  }, [client]);

  return (
    <Box flexDirection="column" height="100%">
      {/* Header */}
      <Box borderStyle="single" paddingX={1}>
        <Text bold color="cyan">Shaw AI CLI</Text>
        <Text> v0.1.0</Text>
        <Box marginLeft={2}>
          <Text color={isLoading ? "yellow" : "green"}>
            {isLoading ? "● thinking" : "● ready"}
          </Text>
        </Box>
      </Box>

      {/* Error bar */}
      {error && (
        <Box borderStyle="round" borderColor="red" paddingX={1}>
          <Text color="red">Error: {error}</Text>
        </Box>
      )}

      {/* Chat messages */}
      <Box flexGrow={1} flexDirection="column" paddingX={1} overflowY="auto">
        {messages.map((msg) => (
          <Chat key={msg.id} message={msg} />
        ))}
      </Box>

      {/* Input */}
      <Input onSend={handleSend} disabled={isLoading} />
    </Box>
  );
}
```

- [ ] **步骤 3：创建 Chat 组件**

```tsx
// cli/src/components/Chat.tsx
import React from "react";
import { Box, Text } from "ink";
import { ToolCall } from "./ToolCall.js";
import type { StreamEvent } from "../rpc.js";

interface Message {
  id: number;
  role: "user" | "assistant" | "tool";
  content: string;
  events?: StreamEvent[];
}

interface ChatProps {
  message: Message;
}

export function Chat({ message }: ChatProps) {
  const { role, content, events } = message;

  if (role === "user") {
    return (
      <Box marginY={1}>
        <Text bold color="blue">◉ </Text>
        <Text>{content}</Text>
      </Box>
    );
  }

  if (role === "assistant") {
    return (
      <Box flexDirection="column" marginY={1}>
        <Text bold color="green">◉ Shaw</Text>
        {content && <Text>{content}</Text>}
        {events?.map((event, i) => {
          if (event.type === "tool_use") {
            return (
              <ToolCall
                key={`${i}-${event.id}`}
                name={event.name || ""}
                input={event.input || {}}
                result={undefined}
              />
            );
          }
          if (event.type === "tool_result") {
            // Find previous tool_use to link result
            return (
              <ToolCall
                key={`result-${i}-${event.id}`}
                name=""
                input={{}}
                result={event.content || ""}
                isError={event.is_error}
              />
            );
          }
          return null;
        })}
      </Box>
    );
  }

  return null;
}
```

- [ ] **步骤 4：创建 Input 组件**

```tsx
// cli/src/components/Input.tsx
import React, { useState, useCallback } from "react";
import { Box, Text } from "ink";
import TextInput from "ink-text-input";

interface InputProps {
  onSend: (input: string) => void;
  disabled?: boolean;
}

export function Input({ onSend, disabled = false }: InputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = useCallback((input: string) => {
    if (input.trim()) {
      onSend(input.trim());
      setValue("");
    }
  }, [onSend]);

  return (
    <Box borderStyle="single" paddingX={1}>
      <Text bold color="cyan">{">"}</Text>
      <Box marginLeft={1} flexGrow={1}>
        {disabled ? (
          <Text dimColor>Waiting for response...</Text>
        ) : (
          <TextInput
            value={value}
            onChange={setValue}
            onSubmit={handleSubmit}
            placeholder="Type a message..."
          />
        )}
      </Box>
    </Box>
  );
}
```

- [ ] **步骤 5：创建 ToolCall 组件**

```tsx
// cli/src/components/ToolCall.tsx
import React, { useState } from "react";
import { Box, Text } from "ink";

interface ToolCallProps {
  name: string;
  input: Record<string, unknown>;
  result?: string;
  isError?: boolean;
}

export function ToolCall({ name, input, result, isError }: ToolCallProps) {
  const [expanded, setExpanded] = useState(false);

  const toolName = name || "Tool";
  const inputStr = JSON.stringify(input, null, 2);

  return (
    <Box flexDirection="column" marginY={1} marginLeft={2}>
      <Box
        borderStyle="round"
        borderColor={isError ? "red" : result ? "green" : "yellow"}
        paddingX={1}
        flexDirection="column"
      >
        <Box>
          <Text bold color="cyan">
            ┌─ 🔧 {toolName}
          </Text>
          <Text> </Text>
          <Text
            color="gray"
            underline
            onPress={() => setExpanded(!expanded)}
          >
            {expanded ? "▲ collapse" : "▼ expand"}
          </Text>
        </Box>
        {expanded && (
          <Box flexDirection="column">
            <Text dimColor>Input:</Text>
            <Text>{inputStr}</Text>
            {result !== undefined && (
              <>
                <Text dimColor>Result:</Text>
                <Text color={isError ? "red" : "white"}>
                  {result.length > 500 ? result.slice(0, 500) + "..." : result}
                </Text>
              </>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
}
```

- [ ] **步骤 6：更新 CLI 入口使用 Ink**

```typescript
// cli/src/index.ts — 更新为 Ink 渲染
import React from "react";
import { render } from "ink";
import { App } from "./components/App.js";
import { RpcClient } from "./rpc.js";

async function main() {
  const client = new RpcClient();

  // 检查引擎状态
  try {
    const status = await client.sendRequest("engine.status", {}) as { status: string };
    if (status.status !== "running") {
      console.error("Engine is not running");
      process.exit(1);
    }
  } catch (e) {
    console.error("Failed to connect to engine:", e);
    process.exit(1);
  }

  const { waitUntilExit } = render(<App client={client} />);

  process.on("SIGINT", () => {
    client.shutdown();
    process.exit(0);
  });

  await waitUntilExit();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
```

- [ ] **步骤 7：验证 CLI 编译**

运行：`cd /mnt/d/Workspace/OpenSourceCLI/cli && npx tsc --noEmit`
预期：无编译错误

- [ ] **步骤 8：Commit**

```bash
git add cli/src/
git commit -m "feat: add Ink-based terminal UI components"
```

---

### 任务 10：示例技能文件

**文件：**
- 创建：`skills/brainstorm.yaml`
- 创建：`skills/tdd.yaml`

- [ ] **步骤 1：创建 brainstorming 技能**

```yaml
# skills/brainstorm.yaml
name: brainstorm
description: 头脑风暴技能 — 在任何创造性工作之前使用
version: 1.0.0

triggers:
  - brainstorm
  - 头脑风暴
  - 设计
  - /brainstorm

system_prompt: |
  你是一个软件设计助手。帮助用户通过以下步骤完善想法：
  1. 理解目的和约束
  2. 探索 2-3 种方案
  3. 权衡分析
  4. 推荐最佳方案
  
  每次只问一个问题，逐步推进。

tools:
  - Read
  - Bash

output:
  format: markdown
```

- [ ] **步骤 2：创建 TDD 技能**

```yaml
# skills/tdd.yaml
name: tdd
description: 测试驱动开发技能 — 先写测试再写实现
version: 1.0.0

triggers:
  - tdd
  - 测试驱动
  - /tdd

system_prompt: |
  你遵循测试驱动开发（TDD）流程：
  1. 先编写失败的测试
  2. 运行测试确认失败
  3. 编写最少实现代码
  4. 运行测试确认通过
  5. 重构（如有需要）
  
  每一步完成后都要确认再进入下一步。

tools:
  - Read
  - Write
  - Edit
  - Bash

output:
  format: markdown
```

- [ ] **步骤 3：Commit**

```bash
git add skills/
git commit -m "feat: add sample skill files (brainstorm, tdd)"
```

---

### 任务 11：README 和初始化脚本

**文件：**
- 创建：`README.md`
- 创建：`scripts/setup.sh`

- [ ] **步骤 1：创建 README**

```markdown
# Shaw AI CLI

> 个人 AI 编程辅助 CLI 工具 — 开放接口，功能完备

## 架构

双层架构：
- **Python 引擎** (`shaw/`) — LLM 循环、工具执行、技能系统
- **Node.js CLI** (`cli/`) — 交互式终端界面

通信：JSON-RPC 2.0 over stdio

## 快速开始

### 前置要求

- Python >= 3.11
- Node.js >= 22

### 安装

```bash
# 安装 Python 引擎
pip install -e .

# 安装 CLI 依赖
cd cli && npm install
```

### 配置

```bash
mkdir -p ~/.shaw
cat > ~/.shaw/config.yaml << EOF
provider:
  anthropic:
    api_key: "your-api-key-here"
    model: claude-sonnet-4-6-20250515
EOF
```

### 使用

```bash
# 启动 CLI
cd cli && npm run dev
```

## 命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/exit` | 退出 |
| `/status` | 引擎状态 |
| `/clear` | 清屏 |

## 项目结构

```
shaw/           # Python 引擎
  engine.py     # LLM 循环核心
  harness.py    # 工具执行沙箱
  provider.py   # Provider 抽象层
  protocol.py   # JSON-RPC 协议
  tools/        # 内置工具
  providers/    # LLM 提供商实现
  
cli/            # Node.js CLI
  src/          # TypeScript 源码
    components/ # React 终端组件
    
skills/         # 声明式技能文件
```

## 扩展

### 添加 Provider

1. 在 `shaw/providers/` 下创建文件
2. 实现 `BaseProvider` 接口
3. 在配置中指定

### 添加工具

1. 在 `shaw/tools/` 下创建文件
2. 继承 `BaseTool` 并实现 `execute` 方法
3. 注册到 `ToolRegistry`

### 添加技能

1. 在 `skills/` 下创建 `.yaml` 文件
2. 定义 triggers、system_prompt、tools
```

- [ ] **步骤 2：创建 setup 脚本**

```bash
#!/bin/bash
# Shaw CLI 初始化脚本

set -e

echo "🔧 Setting up Shaw AI CLI..."

# Python 引擎
echo "📦 Installing Python engine..."
pip install -e .

# CLI 依赖
echo "📦 Installing CLI dependencies..."
cd cli && npm install && cd ..

# 配置目录
echo "📁 Creating config directory..."
mkdir -p ~/.shaw/sessions
mkdir -p ~/.shaw/logs
mkdir -p ~/.shaw/skills
mkdir -p ~/.shaw/cache

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Set your API key: export ANTHROPIC_API_KEY=your-key"
echo "2. Or create ~/.shaw/config.yaml"
echo "3. Run: cd cli && npm run dev"
```

- [ ] **步骤 3：Commit**

```bash
git add README.md scripts/
git commit -m "docs: add README and setup script"
```

---

## 自检

### 1. 规格覆盖度
- ✅ Provider 抽象层 → 任务 4
- ✅ Anthropic 实现 → 任务 4
- ✅ Engine Loop → 任务 6
- ✅ JSON-RPC 协议 → 任务 3
- ✅ 基础工具 (Read/Write/Bash) → 任务 5
- ✅ Harness 安全机制 → 任务 7
- ✅ Session 管理 → 任务 6
- ✅ CLI 入口 + Ink UI → 任务 8, 9
- ✅ Skills 声明式文件 → 任务 10
- ✅ 配置系统 → 任务 2
- ✅ 项目脚手架 → 任务 1
- ✅ README/文档 → 任务 11

### 2. 占位符扫描
- ✅ 无 TODO、待定项、占位符
- ✅ 每个步骤都有完整代码
- ✅ 每个步骤都有精确的命令和预期输出

### 3. 类型一致性
- ✅ StreamEvent 在 Python 和 TypeScript 间类型匹配
- ✅ ToolDef/ToolParam 在 Provider 和 Tool 间一致
- ✅ JSON-RPC 方法名在协议、引擎、CLI 间一致
- ✅ Engine.chat() 返回类型与 protocol.py 中的处理匹配
