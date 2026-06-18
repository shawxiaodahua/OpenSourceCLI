// 解析运行引擎所用 Python 解释器。
//
// 优先级：
//   1. SHAW_PYTHON 环境变量（用户显式指定）
//   2. 项目内 venv：从本文件所在目录向上查找 .venv/bin/python
//      （Windows 下为 .venv/Scripts/python.exe）。README 要求在仓库根目录
//      `python -m venv .venv && pip install -e .`，命中后即可开箱即用，
//      无需每次手动 export SHAW_PYTHON。
//   3. 回退到 PATH 上的 `python`
//
// 这样在未激活 venv 的终端里直接运行 `shaw`，CLI 仍能找到装有 shaw 包的解释器，
// 避免 "No module named shaw"。

import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const VENV_BIN = process.platform === "win32" ? "Scripts/python.exe" : "bin/python";

function findVenvPython(startDir: string): string | null {
  let dir = startDir;
  // 向上最多查找 6 层，足够覆盖 cli/ → 仓库根 的常见布局
  for (let i = 0; i < 6; i++) {
    const candidate = join(dir, ".venv", VENV_BIN);
    if (existsSync(candidate)) return candidate;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

/** 解析引擎 Python 解释器路径。 */
export function resolvePython(): string {
  if (process.env.SHAW_PYTHON) return process.env.SHAW_PYTHON;
  const here = dirname(fileURLToPath(import.meta.url));
  return findVenvPython(here) ?? "python";
}
