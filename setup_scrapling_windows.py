#!/usr/bin/env python3
"""为 @jayyuen66/dsh-scrapling 在 Windows 上准备可用的 Python 运行时。

背景
----
dsh-scrapling 的 Python sidecar 硬性要求 Python 3.14+（见 py/bridge.py 的
MIN_PYTHON）。Windows 上常见的 Python 3.12 会被直接拒绝，表现为宿主日志里
一句没有细节的 `SidecarError: sidecar exited`。

用法
----
    python setup_scrapling_windows.py

脚本做的事：
  1. 用 uv 下载独立的 CPython 3.14 到 %USERPROFILE%\\.dsh-scrapling\\python
  2. 在其中建 venv：%USERPROFILE%\\.dsh-scrapling\\venv
  3. 安装 scrapling[rag]>=0.5,<0.6（含 markdownify，默认 extractionType 需要）
  4. 打印需要写进 profile 的 pythonBin 路径

不做的事：不修改 profile 配置，不安装浏览器（浏览器可选，见 README）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE = Path(os.environ.get("USERPROFILE", Path.home())) / ".dsh-scrapling"
PY_DIR = BASE / "python"
VENV = BASE / "venv"
CACHE = BASE / ".uv-cache"

SCRAPLING_SPEC = "scrapling[rag]>=0.5,<0.6"


def run(argv: list[str], **kwargs) -> None:
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, check=True, **kwargs)


def main() -> int:
    BASE.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(CACHE)
    env["UV_PYTHON_INSTALL_DIR"] = str(PY_DIR)

    # 1. 下载独立 Python 3.14
    run(["uv", "python", "install", "3.14"], env=env)

    # 2. 找到刚装好的解释器
    candidates = sorted(PY_DIR.glob("cpython-3.14*/python.exe"))
    if not candidates:
        print("未找到安装好的 Python 3.14，检查 uv 输出", file=sys.stderr)
        return 1
    base_python = candidates[-1]
    print(f"Python: {base_python}")

    # 3. 建 venv
    if not (VENV / "Scripts" / "python.exe").exists():
        run(["uv", "venv", "--python", str(base_python), str(VENV)], env=env)

    venv_python = VENV / "Scripts" / "python.exe"

    # 4. 装 Scrapling
    run(
        ["uv", "pip", "install", "--python", str(venv_python), SCRAPLING_SPEC],
        env=env,
    )

    # 5. 验证
    check = subprocess.run(
        [str(venv_python), "-I", "-c",
         "import sys,scrapling;print(sys.version.split()[0]);print('scrapling',scrapling.__version__)"],
        capture_output=True, text=True,
    )
    print(check.stdout.strip() or check.stderr.strip())

    print()
    print("=" * 60)
    print("把下面这个路径填进 dsh-scrapling 设置的 pythonBin：")
    print(venv_python)
    print("=" * 60)
    return 0 if check.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
