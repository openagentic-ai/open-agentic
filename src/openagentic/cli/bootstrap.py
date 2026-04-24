"""模块说明（中文）：`src/openagentic/cli/bootstrap.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from openagentic.cli.platform_adapter import CLI_PLATFORM


def _build_source_fingerprint(pyproject: Path, src_dir: Path) -> str:
    """Only track pyproject.toml — editable install means .py changes take effect
    immediately without reinstall.  Reinstall is only needed when dependencies or
    package metadata change."""
    h = hashlib.sha256()
    try:
        stat = pyproject.stat()
    except OSError:
        return ""
    h.update(pyproject.as_posix().encode("utf-8"))
    h.update(str(stat.st_size).encode("ascii"))
    h.update(str(stat.st_mtime_ns).encode("ascii"))
    return h.hexdigest()


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

    current_fingerprint = _build_source_fingerprint(pyproject, src_dir)
    last_fingerprint = ""
    if stamp_file.exists():
        try:
            raw = stamp_file.read_text(encoding="utf-8").strip()
            if raw.startswith("{"):
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    last_fingerprint = str(payload.get("fingerprint", ""))
            else:
                # legacy numeric stamp format; force one-time upgrade install.
                last_fingerprint = ""
        except (OSError, ValueError, json.JSONDecodeError):
            last_fingerprint = ""

    if last_fingerprint == current_fingerprint:
        return

    print("[bootstrap] 检测到本地源码更新，正在执行: pip install -e .")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print("[WARN] 自动安装失败，请手动执行: pip install -e .")
        err = (result.stderr or result.stdout or "").strip()
        if err:
            print(err[:800])
        return

    stamp_dir.mkdir(parents=True, exist_ok=True)
    stamp_file.write_text(
        json.dumps({"fingerprint": current_fingerprint}, ensure_ascii=False),
        encoding="utf-8",
    )
    print("[bootstrap] 已完成自动安装。")
