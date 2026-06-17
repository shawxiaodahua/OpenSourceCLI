import React from "react";
import { Box, Text } from "ink";
import type { ToolEvent } from "./MessageList.js";

interface ToolCallProps {
  event: ToolEvent;
}

export function ToolCall({ event }: ToolCallProps) {
  if (event.kind === "tool_result") {
    return (
      <Box marginLeft={2} flexDirection="column">
        <Text color={event.isError ? "red" : "gray"} dimColor>
          ↳ {event.isError ? "error" : "result"}:{" "}
          {truncate(event.content ?? "", 200)}
        </Text>
      </Box>
    );
  }

  // tool_use
  const inputStr = JSON.stringify(event.input ?? {});
  return (
    <Box marginLeft={2} flexDirection="column">
      <Box>
        <Text color="cyan" bold>🔧 {event.name}</Text>
        <Text dimColor> {truncate(inputStr, 100)}</Text>
      </Box>
    </Box>
  );
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max) + "…";
}
