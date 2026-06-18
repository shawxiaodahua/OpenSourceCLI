import React from "react";
import { render } from "ink";
import { App } from "./components/App.js";
import { RpcClient } from "./rpc.js";
import { resolvePython } from "./python.js";

async function main() {
  // 引擎模块参数：默认 python -m shaw；可由环境变量覆盖
  const engineArgs = process.env.SHAW_ENGINE_ARGS
    ? process.env.SHAW_ENGINE_ARGS.split(/\s+/).filter(Boolean)
    : ["-m", "shaw"];
  // 解析解释器：SHAW_PYTHON > 项目 .venv/bin/python > PATH 上的 python
  const python = resolvePython();

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
      `提示: 使用解释器 ${python} 无法导入 shaw。请在该环境执行 \`pip install -e .\`，` +
        "或 export SHAW_PYTHON 指向已安装 shaw 的解释器；并配置 ~/.shaw/config.yaml (api_key)\n",
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
