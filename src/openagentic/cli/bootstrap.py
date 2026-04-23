"""Optional editable-install bootstrap for the CLI."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from openagentic.cli.platform_adapter import CLI_PLATFORM


def maybe_auto_install_editable() -> None:
    """Auto-run `pip install -e .` when local source changed."""
    if CLI_PLATFORM.should_skip_auto_editable_install():
        return

    # openagentic/cli/bootstrap.py -> repo root
    project_root = Path(__file__).resolve().parents[3]
    pyproject = project_root / "pyproject.toml"
    src_dir = project_root / "src"
    stamp_dir = project_root / ".openagentic"
    stamp_file = stamp_dir / ".last_editable_install"

    if not pyproject.exists() or not src_dir.exists():
        return

    latest_mtime = pyproject.stat().st_mtime
    for path in src_dir.rglob("*.py"):
        try:
            latest_mtime = max(latest_mtime, path.stat().st_mtime)
        except OSError:
            continue

    last_installed = 0.0
    if stamp_file.exists():
        try:
            last_installed = float(stamp_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            last_installed = 0.0

    if last_installed >= latest_mtime:
        return

    print("[bootstrap] 检测到本地源码更新，正在执行: pip install -e .")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        cwd=str(project_root),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print("[WARN] 自动安装失败，请手动执行: pip install -e .")
        err = (result.stderr or result.stdout or "").strip()
        if err:
            print(err[:800])
        return

    stamp_dir.mkdir(parents=True, exist_ok=True)
    stamp_file.write_text(str(time.time()), encoding="utf-8")
    print("[bootstrap] 已完成自动安装。")
