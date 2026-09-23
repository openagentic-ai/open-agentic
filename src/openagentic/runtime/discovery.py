from __future__ import annotations

import os
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class LocalRuntime:
    name: str
    command: str | None
    available: bool
    hardware: dict[str, str]


def discover_local_runtimes() -> list[LocalRuntime]:
    """发现本机可用的本地模型运行时，不读取或上传 API 密钥。"""
    gpu = os.environ.get("OPENAGENTIC_GPU", "unknown")
    candidates = ("ollama", "llama-server", "lmstudio")
    return [
        LocalRuntime(name, shutil.which(name), shutil.which(name) is not None, {"gpu": gpu})
        for name in candidates
    ]
