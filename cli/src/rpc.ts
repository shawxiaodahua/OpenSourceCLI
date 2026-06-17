// JSON-RPC 2.0 stdio 客户端 — 启动 Python 引擎子进程并双向通信。
//
// 关键设计：stdout 上只有 *一个* readline 持久监听器。普通响应按 id 匹配
// pending 请求；流式响应（chat.send）的事件按 streamId 路由到对应的异步迭代器。
// 这样避免了原方案中每次流式调用新建 readline 导致的事件抢夺问题。

import { ChildProcess, spawn } from "node:child_process";
import { createInterface, Interface } from "node:readline";

export type StreamEventType =
  | "stream_start"
  | "stream_end"
  | "text"
  | "thinking"
  | "tool_use"
  | "tool_result"
  | "error";

export interface StreamEvent {
  type: StreamEventType;
  // JSON-RPC 响应封套
  jsonrpc?: string;
  id?: number;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
  // 事件字段
  content?: string;
  name?: string;
  input?: Record<string, unknown>;
  id_?: string; // tool_use id（避免与 jsonrpc id 冲突，引擎侧字段名为 id）
  is_error?: boolean;
  message?: string;
  // 流式路由标记
  streamId?: number;
}

type Pending = {
  resolve: (v: unknown) => void;
  reject: (e: Error) => void;
};

type StreamController = {
  push: (event: StreamEvent) => void;
};

export interface RpcClientOptions {
  /** Python 解释器，默认 python */
  python?: string;
  /** 引擎模块参数，默认 ["-m", "shaw"] */
  engineArgs?: string[];
  /** 引擎工作目录，默认 process.cwd() */
  cwd?: string;
  /** 是否继承 stderr，默认 true（便于查看引擎日志） */
  inheritStderr?: boolean;
}

export class RpcClient {
  private process: ChildProcess;
  private rl: Interface;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private streams = new Map<number, StreamController>();
  private closed = false;

  constructor(opts: RpcClientOptions = {}) {
    const python = opts.python ?? "python";
    const args = opts.engineArgs ?? ["-m", "shaw"];
    this.process = spawn(python, args, {
      stdio: ["pipe", "pipe", opts.inheritStderr === false ? "ignore" : "inherit"],
      cwd: opts.cwd ?? process.cwd(),
    });

    this.rl = createInterface({ input: this.process.stdout!, crlfDelay: Infinity });
    this.rl.on("line", (line) => this.handleLine(line));

    this.process.on("exit", (code) => {
      this.closed = true;
      if (code !== null && code !== 0) {
        // 通知所有等待中的请求
        const err = new Error(`Engine exited with code ${code}`);
        for (const p of this.pending.values()) p.reject(err);
        for (const s of this.streams.values()) s.push({ type: "error", message: err.message });
      }
    });
  }

  private handleLine(line: string): void {
    const trimmed = line.trim();
    if (!trimmed) return;
    let msg: any;
    try {
      msg = JSON.parse(trimmed);
    } catch {
      return; // 忽略畸形行
    }

    // 流式事件：携带 streamId 路由
    if (msg.streamId !== undefined && this.streams.has(msg.streamId)) {
      this.streams.get(msg.streamId)!.push(msg as StreamEvent);
      if (msg.type === "stream_end" || msg.type === "error") {
        this.streams.delete(msg.streamId);
      }
      return;
    }

    // 普通 JSON-RPC 响应：按 id 匹配
    if (msg.id !== undefined && this.pending.has(msg.id)) {
      const { resolve, reject } = this.pending.get(msg.id)!;
      this.pending.delete(msg.id);
      if (msg.error) {
        reject(new Error(msg.error.message ?? "Unknown RPC error"));
      } else {
        resolve(msg.result);
      }
    }
  }

  /** 发送普通请求并等待结果。 */
  async request(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    if (this.closed) throw new Error("Engine is not running");
    const id = this.nextId++;
    const frame = JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n";
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.process.stdin!.write(frame);
    });
  }

  /** 发送流式请求，返回异步迭代器逐个产出事件。 */
  async *stream(
    method: string,
    params: Record<string, unknown> = {},
  ): AsyncGenerator<StreamEvent> {
    if (this.closed) throw new Error("Engine is not running");
    const id = this.nextId++;
    const streamId = id; // 用同一 id 标识本流

    const queue: StreamEvent[] = [];
    let resolveWaiter: (() => void) | null = null;
    let done = false;

    this.streams.set(streamId, {
      push: (ev) => {
        queue.push(ev);
        if (resolveWaiter) {
          const w = resolveWaiter;
          resolveWaiter = null;
          w();
        }
      },
    });

    const frame = JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n";
    this.process.stdin!.write(frame);

    try {
      while (true) {
        if (queue.length === 0) {
          if (done) break;
          await new Promise<void>((r) => (resolveWaiter = r));
        }
        while (queue.length > 0) {
          const ev = queue.shift()!;
          yield ev;
          if (ev.type === "stream_end" || ev.type === "error") {
            done = true;
          }
        }
        if (done) break;
      }
    } finally {
      this.streams.delete(streamId);
    }
  }

  /** 发送通知（无响应）。 */
  notify(method: string, params: Record<string, unknown> = {}): void {
    const frame = JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n";
    this.process.stdin!.write(frame);
  }

  /** 优雅关闭引擎。 */
  shutdown(): void {
    try {
      this.notify("shutdown", {});
    } catch {
      /* ignore */
    }
    setTimeout(() => {
      try {
        this.process.kill();
      } catch {
        /* ignore */
      }
    }, 1000);
  }
}
