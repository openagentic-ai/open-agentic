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
        print("[bootstrap] 鏈娴嬪埌宸插畨瑁呯殑 openagentic锛屾鍦ㄦ墽琛? pip install -e .", flush=True)
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(root)],
            cwd=str(root),
        )
        if r.returncode != 0:
            print(
                "[ERROR] 鑷姩瀹夎澶辫触銆傝鍦ㄤ粨搴撴牴鐩綍鎵ц:\n"
                f"  {sys.executable} -m pip install -e .",
                file=sys.stderr,
            )
            sys.exit(r.returncode or 1)
        try:
            from openagentic.cli import main as cli_main
        except ModuleNotFoundError:
            # Same interpreter 鏈夋椂浠嶆湭鍒锋柊璺緞锛岀敤瀛愯繘绋嬪惎鍔?CLI
            sys.exit(
                subprocess.call(
                    [sys.executable, "-m", "openagentic.cli", *sys.argv[1:]],
                    cwd=str(root),
                )
            )
    cli_main()
