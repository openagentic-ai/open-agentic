"""Console entrypoint: works even when `openagentic` is not yet importable (fresh clone / broken venv)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    # .../src/openagentic_entry/__init__.py -> repo root
    return Path(__file__).resolve().parents[2]


def main() -> None:
    """Install editable package if needed, then run the real CLI."""
    root = _repo_root()
    try:
        from openagentic.cli import main as cli_main
    except ModuleNotFoundError:
        print("[bootstrap] 未检测到已安装的 openagentic，正在执行: pip install -e .", flush=True)
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(root)],
            cwd=str(root),
        )
        if r.returncode != 0:
            print(
                "[ERROR] 自动安装失败。请在仓库根目录执行:\n"
                f"  {sys.executable} -m pip install -e .",
                file=sys.stderr,
            )
            sys.exit(r.returncode or 1)
        try:
            from openagentic.cli import main as cli_main
        except ModuleNotFoundError:
            # Same interpreter 有时仍未刷新路径，用子进程启动 CLI
            sys.exit(
                subprocess.call(
                    [sys.executable, "-m", "openagentic.cli", *sys.argv[1:]],
                    cwd=str(root),
                )
            )
    cli_main()
