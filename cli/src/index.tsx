import React from "react";
import { render } from "ink";
import { App } from "./components/App.js";
import { RpcClient } from "./rpc.js";

async function main() {
  // 引擎模块参数：默认 python -m shaw；可由环境变量覆盖
  const engineArgs = process.env.SHAW_ENGINE_ARGS
    ? process.env.SHAW_ENGINE_ARGS.split(/\s+/).filter(Boolean)
    : ["-m", "shaw"];
  const python = process.env.SHAW_PYTHON ?? "python";

  const client = new RpcClient({ python, engineArgs });

  // 启动横幅（写到 stderr，避免污染 JSON-RPC 的 stdout 通道）
  process.stderr.write("Shaw AI CLI v0.1.0 — connecting to engine...\n");

  // 探测引擎是否就绪
  let model = "unknown";
  try {
    const status = (await client.request("engine.status")) as {
      status: string;
      provider: string;
    };
    if (status.status !== "running") {
      process.stderr.write("Engine is not running\n");
      client.shutdown();
      process.exit(1);
    }
    model = status.provider;
  } catch (e) {
    process.stderr.write(`Failed to connect to engine: ${e}\n`);
    process.stderr.write(
      "提示: 确保已 `pip install -e .` 并配置了 ~/.shaw/config.yaml (api_key)\n",
    );
    client.shutdown();
    process.exit(1);
  }

  const { waitUntilExit } = render(<App client={client} model={model} />);

  process.on("SIGINT", () => {
    client.shutdown();
    process.exit(0);
  });

  await waitUntilExit();
  client.shutdown();
}

main().catch((e) => {
  process.stderr.write(String(e) + "\n");
  process.exit(1);
});
