"""IM Adapter 注册中心。

替代 extensions/channels/__init__.py。客户端(Web/Android)不在此,走 src/openagentic/gateway/。

设计原则(对齐 ADR-001 §1, §3):
- 零核心依赖 — adapter 不 import openagentic.application 之外的内部模块
- 凭据自检 — 各 adapter try_create_*() env 缺失返回 None
- 加载隔离 — 单个 adapter 失败不影响其他

实现见 Phase 1+。Phase 0 仅占位。
"""
from __future__ import annotations
__all__: list[str] = []
