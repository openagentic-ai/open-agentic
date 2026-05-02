"""AdapterRegistry 测试。

覆盖:
- register / get / all 基本功能
- start_all 顺序调用,单个失败不影响其他(隔离)
- stop_all 隔离失败
- discover_from_env: env 命中 / 未命中 / 模块无 create_adapter / 工厂抛异常
"""
from __future__ import annotations

import sys
import types

import pytest

from extensions.adapters.registry import AdapterRegistry, discover_from_env


class _FakeAdapter:
    def __init__(self, adapter_id: str, *, fail_start: bool = False, fail_stop: bool = False):
        self.adapter_id = adapter_id
        self.started = False
        self.stopped = False
        self._fail_start = fail_start
        self._fail_stop = fail_stop

    async def start(self, orchestrator) -> None:
        if self._fail_start:
            raise RuntimeError(f"{self.adapter_id} start boom")
        self.started = True

    async def stop(self) -> None:
        if self._fail_stop:
            raise RuntimeError(f"{self.adapter_id} stop boom")
        self.stopped = True


# ── 基本 CRUD ───────────────────────────────────────────────────────────

def test_register_and_get():
    reg = AdapterRegistry()
    a = _FakeAdapter("feishu")
    reg.register(a)
    assert reg.get("feishu") is a
    assert reg.get("nope") is None
    assert list(reg.all()) == [a]


def test_register_overrides_same_id():
    reg = AdapterRegistry()
    a1 = _FakeAdapter("feishu")
    a2 = _FakeAdapter("feishu")
    reg.register(a1)
    reg.register(a2)
    assert reg.get("feishu") is a2
    assert len(list(reg.all())) == 1


# ── 启停隔离 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_all_isolates_failures():
    reg = AdapterRegistry()
    ok1 = _FakeAdapter("feishu")
    bad = _FakeAdapter("wecom", fail_start=True)
    ok2 = _FakeAdapter("dingtalk")
    for a in (ok1, bad, ok2):
        reg.register(a)
    await reg.start_all(orchestrator=object())
    assert ok1.started is True
    assert bad.started is False
    assert ok2.started is True   # 关键:bad 失败不影响后续


@pytest.mark.asyncio
async def test_stop_all_isolates_failures():
    reg = AdapterRegistry()
    ok = _FakeAdapter("feishu")
    bad = _FakeAdapter("wecom", fail_stop=True)
    reg.register(ok)
    reg.register(bad)
    await reg.stop_all()
    assert ok.stopped is True
    # bad 抛异常被吞,不传播


# ── discover_from_env ─────────────────────────────────────────────────

def _install_fake_module(name: str, *, factory=None, raise_on_import: bool = False):
    """注入一个假 module 到 sys.modules。"""
    if raise_on_import:
        # importlib 走 sys.modules cache;为了让 import_module 抛异常,
        # 需要清缓存 + 注册一个 import-time 抛错的 finder。简化:直接放一个 sentinel,
        # 配合外层 monkeypatch importlib.import_module。
        return
    mod = types.ModuleType(name)
    if factory is not None:
        mod.create_adapter = factory
    sys.modules[name] = mod
    # 父级也要存在
    if "." in name:
        parent = name.rsplit(".", 1)[0]
        sys.modules.setdefault(parent, types.ModuleType(parent))


def _cleanup_fake_modules(*names: str) -> None:
    for n in names:
        sys.modules.pop(n, None)


def test_discover_from_env_loads_when_var_set():
    _install_fake_module(
        "extensions.adapters.feishu",
        factory=lambda: _FakeAdapter("feishu"),
    )
    try:
        reg = discover_from_env(env={"FEISHU_APP_ID": "x"})
        assert reg.get("feishu") is not None
        assert reg.get("feishu").adapter_id == "feishu"
    finally:
        _cleanup_fake_modules("extensions.adapters.feishu")


def test_discover_from_env_skips_when_var_missing():
    reg = discover_from_env(env={})
    assert list(reg.all()) == []


def test_discover_from_env_skips_module_without_factory():
    _install_fake_module("extensions.adapters.wecom", factory=None)
    try:
        reg = discover_from_env(env={"WECOM_CORP_ID": "x"})
        assert list(reg.all()) == []
    finally:
        _cleanup_fake_modules("extensions.adapters.wecom")


def test_discover_from_env_skips_when_factory_raises():
    def boom():
        raise RuntimeError("config invalid")
    _install_fake_module("extensions.adapters.dingtalk", factory=boom)
    try:
        reg = discover_from_env(env={"DINGTALK_APP_KEY": "x"})
        assert list(reg.all()) == []
    finally:
        _cleanup_fake_modules("extensions.adapters.dingtalk")


def test_discover_from_env_loads_multiple():
    _install_fake_module(
        "extensions.adapters.feishu",
        factory=lambda: _FakeAdapter("feishu"),
    )
    _install_fake_module(
        "extensions.adapters.wecom",
        factory=lambda: _FakeAdapter("wecom"),
    )
    try:
        reg = discover_from_env(env={"FEISHU_APP_ID": "x", "WECOM_CORP_ID": "y"})
        ids = sorted(a.adapter_id for a in reg.all())
        assert ids == ["feishu", "wecom"]
    finally:
        _cleanup_fake_modules(
            "extensions.adapters.feishu", "extensions.adapters.wecom",
        )
