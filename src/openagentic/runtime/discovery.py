from __future__ import annotations

import os
import shutil
import asyncio
from collections.abc import Sequence
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


def detect_hardware() -> dict[str, str]:
    gpu = os.environ.get("OPENAGENTIC_GPU")
    if not gpu:
        gpu = "nvidia" if shutil.which("nvidia-smi") else "cpu"
    return {"cpu_count": str(os.cpu_count() or 1), "gpu": gpu}


class RuntimeManager:
    """管理本地模型运行时子进程生命周期，不接触云端 API key。"""

    def __init__(self) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def start(self, name: str, command: Sequence[str]) -> None:
        if name in self._processes and self._processes[name].returncode is None:
            return
        self._processes[name] = await asyncio.create_subprocess_exec(*command)

    async def stop(self, name: str) -> None:
        process = self._processes.pop(name, None)
        if process is not None and process.returncode is None:
            process.terminate()
            await process.wait()
