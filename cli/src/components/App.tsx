import React, { useCallback, useRef, useState } from "react";
import { Box, Text, useApp, useInput } from "ink";
import TextInput from "ink-text-input";
import { RpcClient, StreamEvent } from "../rpc.js";
import { MessageList, type UiMessage } from "./MessageList.js";

interface AppProps {
  client: RpcClient;
  model: string;
}

export function App({ client, model }: AppProps) {
  const { exit } = useApp();
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tokenInfo, setTokenInfo] = useState<string>("");
  // 用 ref 维护消息 id 与当前 assistant 消息，避免闭包陈旧值
  const nextId = useRef(1);
  const currentAssistant = useRef<UiMessage | null>(null);

  const runCommand = useCallback(
    (raw: string) => {
      const cmd = raw.trim();
      if (cmd === "/exit" || cmd === "/quit") {
        client.shutdown();
        exit();
        return;
      }
      if (cmd === "/clear") {
        setMessages([]);
        return;
      }
      if (cmd === "/help") {
        setMessages((prev) => [
          ...prev,
          {
            id: nextId.current++,
            role: "system",
            content:
              "命令: /help /clear /exit /status /skills /sessions /model <name>",
          },
        ]);
        return;
      }
      if (cmd === "/status") {
        client
          .request("engine.status")
          .then((s) =>
            setMessages((prev) => [
              ...prev,
              {
                id: nextId.current++,
                role: "system",
                content: JSON.stringify(s, null, 2),
              },
            ]),
          )
          .catch((e) => setError(String(e)));
        return;
      }
      if (cmd === "/skills") {
        client
          .request("skill.list")
          .then((s) =>
            setMessages((prev) => [
              ...prev,
              {
                id: nextId.current++,
                role: "system",
                content: "技能:\n" + JSON.stringify(s, null, 2),
              },
            ]),
          )
          .catch((e) => setError(String(e)));
        return;
      }
      // 普通聊天
      sendMessage(cmd);
    },
    [client, exit],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      const userMsg: UiMessage = {
        id: nextId.current++,
        role: "user",
        content: text,
      };
      const assistantMsg: UiMessage = {
        id: nextId.current++,
        role: "assistant",
        content: "",
        events: [],
      };
      currentAssistant.current = assistantMsg;
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setLoading(true);
      setError(null);

      try {
        for await (const ev of client.stream("chat.send", { message: text })) {
          updateAssistant(ev);
          if (ev.type === "error") {
            setError(ev.message ?? "unknown error");
          }
        }
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    },
    [client],
  );

  const updateAssistant = useCallback((ev: StreamEvent) => {
    const target = currentAssistant.current;
    if (!target) return;
    if (ev.type === "text" && ev.content) {
      target.content += ev.content;
    } else if (ev.type === "tool_use") {
      target.events = [
        ...(target.events ?? []),
        { kind: "tool_use", name: ev.name ?? "", input: ev.input ?? {}, id: ev.id_ ?? "" },
      ];
    } else if (ev.type === "tool_result") {
      target.events = [
        ...(target.events ?? []),
        { kind: "tool_result", id: ev.id_ ?? "", content: ev.content ?? "", isError: ev.is_error },
      ];
    } else if (ev.type === "thinking" && ev.content) {
      target.thinking = (target.thinking ?? "") + ev.content;
    }
    // 触发渲染：用新对象替换
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === target.id);
      if (idx < 0) return prev;
      const next = [...prev];
      next[idx] = { ...target };
      return next;
    });
  }, []);

  useInput((_, key) => {
    if (key.ctrl && _.toLowerCase() === "c") {
      client.shutdown();
      exit();
    }
  });

  return (
    <Box flexDirection="column" height="100%">
      <Box borderStyle="single" paddingX={1}>
        <Text bold color="cyan"> Shaw AI CLI</Text>
        <Text dimColor> v0.1.0</Text>
        <Box marginLeft={2}>
          <Text color={loading ? "yellow" : "green"}>
            {loading ? "● thinking" : "● ready"}
          </Text>
        </Box>
        <Box marginLeft={2}>
          <Text dimColor>model: {model}</Text>
        </Box>
      </Box>

      {error && (
        <Box paddingX={1}>
          <Text color="red">⚠ {error}</Text>
        </Box>
      )}

      <Box flexGrow={1} flexDirection="column" paddingX={1}>
        <MessageList messages={messages} />
        {loading && (
          <Text color="yellow" dimColor>▋</Text>
        )}
      </Box>

      <Box borderStyle="single" paddingX={1}>
        <Text bold color="cyan">›</Text>
        <Box marginLeft={1} flexGrow={1}>
          {loading ? (
            <Text dimColor>waiting for response...</Text>
          ) : (
            <TextInput
              value={input}
              onChange={setInput}
              onSubmit={(v) => {
                if (v.trim()) {
                  setInput("");
                  runCommand(v);
                }
              }}
              placeholder="输入消息或 /help 查看命令"
            />
          )}
        </Box>
      </Box>
      {tokenInfo ? (
        <Box paddingX={1}>
          <Text dimColor>{tokenInfo}</Text>
        </Box>
      ) : null}
    </Box>
  );
}
