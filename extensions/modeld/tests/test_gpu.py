"""显存预检契约——把 2026-09-22 那次事故固化成回归测试。

vLLM 的准入规则是：free >= gpu_memory_utilization × usable_total。
usable_total = nvidia-smi total − 驱动/CUDA 上下文开销（约 459 MiB）。
不满足则报 "Engine core initialization failed"，真因埋在 systemd journal 里，
本模块的作用就是提前把它变成一句人话。
"""

from __future__ import annotations

from app.gpu import check_capacity


def test_passes_when_plenty_free():
    v = check_capacity(free_mib=24102, total_mib=24564, utilization=0.95)
    assert v.ok is True
    assert v.shortfall_mib == 0


def test_reports_shortfall_when_not_enough():
    # 空卡 24102 空闲，reranker 走后剩 15535
    v = check_capacity(free_mib=15535, total_mib=24564, utilization=0.95)
    assert v.ok is False
    assert v.shortfall_mib > 0


def test_regression_20260922_reranker_contention():
    """2026-09-22 事故现场：reranker 占 8.4G，27B 起不来。

    journal 原文：Free memory on device cuda:0 (21.37/23.54 GiB) ...
                  less than desired GPU memory utilization (0.95, 22.37 GiB)
    """
    v = check_capacity(free_mib=15535, total_mib=24564, utilization=0.95)
    assert v.ok is False
    # 可用总量应按 23.54 GiB（= 24105 MiB）计，不是 24564
    assert 24000 <= v.usable_mib <= 24200
    # 需求量应按 22.37 GiB（= 22907 MiB）计
    assert 22850 <= v.required_mib <= 22970


def test_utilization_never_exceeds_total():
    v = check_capacity(free_mib=24102, total_mib=24564, utilization=1.0)
    assert v.required_mib <= v.total_mib
