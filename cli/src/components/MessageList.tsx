import React from "react";
import { Box, Text } from "ink";
import { ToolCall } from "./ToolCall.js";

export interface ToolEvent {
  kind: "tool_use" | "tool_result";
  name?: string;
  input?: Record<string, unknown>;
  id: string;
  content?: string;
  isError?: boolean;
}

export interface UiMessage {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  thinking?: string;
  events?: ToolEvent[];
}

export function MessageList({ messages }: { messages: UiMessage[] }) {
  return (
    <Box flexDirection="column">
      {messages.map((m) => (
        <MessageView key={m.id} message={m} />
      ))}
    </Box>
  );
}

function MessageView({ message }: { message: UiMessage }) {
  if (message.role === "user") {
    return (
      <Box marginY={0}>
        <Text bold color="blue">◉ </Text>
        <Text>{message.content}</Text>
      </Box>
    );
  }

  if (message.role === "system") {
    return (
      <Box marginY={0}>
        <Text dimColor>{message.content}</Text>
      </Box>
    );
  }

  // assistant
  return (
    <Box flexDirection="column" marginY={0}>
      <Text bold color="green">◉ Shaw</Text>
      {message.thinking ? (
        <Box marginLeft={2}>
          <Text dimColor italic>{message.thinking}</Text>
        </Box>
      ) : null}
      {message.content ? <Text>{message.content}</Text> : null}
      {(message.events ?? []).map((ev, i) => (
        <ToolCall key={`${message.id}-${i}`} event={ev} />
      ))}
    </Box>
  );
}
