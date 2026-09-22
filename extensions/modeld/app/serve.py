"""模块说明（中文）：`app/serve.py`。

守护进程入口：读配置 → 建 app → 起 uvicorn。
"""

from __future__ import annotations

import os

import uvicorn

from app.config import load_config
from app.main import create_app

DEFAULT_CONFIG = "/opt/modeld/modeld.yaml"


def main() -> None:
    path = os.environ.get("MODELD_CONFIG", DEFAULT_CONFIG)
    cfg = load_config(path)
    uvicorn.run(create_app(cfg), host="127.0.0.1", port=9998, log_level="info")


if __name__ == "__main__":
    main()
