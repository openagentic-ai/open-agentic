"""模块说明（中文）：`app/gpu.py`。

显存查询与准入预检。

vLLM 的准入规则：free >= gpu_memory_utilization × usable_total，
其中 usable_total = nvidia-smi total − 驱动/CUDA 上下文开销。
不满足时 vLLM 只抛 "Engine core initialization failed"，真因埋在 systemd journal 里。
本模块把这件事提前变成一句人话。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

DEFAULT_DRIVER_OVERHEAD_MIB = 459


@dataclass(frozen=True)
class CapacityVerdict:
    ok: bool
    free_mib: int
    total_mib: int
    usable_mib: int
    required_mib: int
    shortfall_mib: int

    def reason(self) -> str:
        if self.ok:
            return f"显存充足（空闲 {self.free_mib} MiB / 需要 {self.required_mib} MiB）"
        return (
            f"显存不足：空闲 {self.free_mib} MiB，需要 {self.required_mib} MiB"
            f"（缺口 {self.shortfall_mib} MiB）"
        )


def check_capacity(
    free_mib: int,
    total_mib: int,
    utilization: float,
    driver_overhead_mib: int = DEFAULT_DRIVER_OVERHEAD_MIB,
) -> CapacityVerdict:
    usable = max(0, total_mib - driver_overhead_mib)
    required = round(utilization * usable)
    shortfall = max(0, required - free_mib)
    return CapacityVerdict(
        ok=shortfall == 0,
        free_mib=free_mib,
        total_mib=total_mib,
        usable_mib=usable,
        required_mib=required,
        shortfall_mib=shortfall,
    )


@dataclass(frozen=True)
class GpuUser:
    pid: int
    name: str
    used_mib: int


@dataclass(frozen=True)
class GpuState:
    total_mib: int
    used_mib: int
    free_mib: int
    users: tuple[GpuUser, ...]


def _run(cmd: list[str], timeout: float = 10.0) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True).stdout


def query_state() -> GpuState:
    """读一次显存全貌（含占用者），用于诊断和预检。"""
    mem = _run([
        "nvidia-smi",
        "--query-gpu=memory.total,memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ]).strip().splitlines()[0]
    total, used, free = (int(x.strip()) for x in mem.split(","))

    users: list[GpuUser] = []
    try:
        apps = _run([
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ]).strip()
        for line in apps.splitlines():
            if not line.strip():
                continue
            pid_s, name, mib_s = (p.strip() for p in line.split(",", 2))
            if not pid_s.isdigit():
                continue
            users.append(GpuUser(pid=int(pid_s), name=name, used_mib=int(mib_s)))
    except Exception:
        pass

    return GpuState(total_mib=total, used_mib=used, free_mib=free, users=tuple(users))
