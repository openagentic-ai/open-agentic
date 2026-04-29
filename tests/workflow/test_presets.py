"""Phase 7 系统预设工作流：loader + sync + 实际预设文件健全度测试。

不依赖真实 DB——上层集成由 tests/workflow/test_workflow_api.py 与 e2e 覆盖。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from openagentic.workflow import presets, service


# ---------- 单文件 YAML 解析 ----------


def test_load_preset_yaml_returns_dict_for_valid_file(tmp_path):
    p = tmp_path / "ok.yaml"
    p.write_text(yaml.safe_dump({
        "slug": "demo.x",
        "name": "demo",
        "version": 1,
        "definition": {
            "nodes": [{"id": "a", "type": "value", "config": {"value": "hi"}}],
            "edges": [],
        },
    }), encoding="utf-8")
    data = presets._load_preset_yaml(p)
    assert data is not None
    assert data["slug"] == "demo.x"


def test_load_preset_yaml_skips_missing_required(tmp_path):
    p = tmp_path / "bad.yaml"
    # 缺 slug/version/definition
    p.write_text(yaml.safe_dump({"name": "broken"}), encoding="utf-8")
    assert presets._load_preset_yaml(p) is None


def test_load_preset_yaml_skips_invalid_yaml(tmp_path):
    p = tmp_path / "garbage.yaml"
    p.write_text("not: valid: yaml: [", encoding="utf-8")
    assert presets._load_preset_yaml(p) is None


# ---------- 目录扫描 ----------


def test_scan_presets_returns_empty_when_dir_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(presets, "PRESETS_DIR", tmp_path / "nonexistent")
    assert presets._scan_presets() == []


def test_scan_presets_dedupe_by_slug_with_later_winning(monkeypatch, tmp_path):
    monkeypatch.setattr(presets, "PRESETS_DIR", tmp_path)
    # 两份同 slug 文件，后者（按文件名排序）覆盖前者
    (tmp_path / "01_first.yaml").write_text(yaml.safe_dump({
        "slug": "dup", "name": "v1", "version": 1,
        "definition": {"nodes": [{"id": "n", "type": "value", "config": {}}], "edges": []},
    }), encoding="utf-8")
    (tmp_path / "02_second.yaml").write_text(yaml.safe_dump({
        "slug": "dup", "name": "v2", "version": 2,
        "definition": {"nodes": [{"id": "n", "type": "value", "config": {}}], "edges": []},
    }), encoding="utf-8")
    out = presets._scan_presets()
    assert len(out) == 1
    assert out[0]["name"] == "v2"


# ---------- DB upsert ----------


@pytest.mark.asyncio
async def test_load_presets_creates_when_absent(monkeypatch):
    """slug 在 DB 不存在 → 新增"""
    monkeypatch.setattr(presets, "_scan_presets", lambda: [{
        "slug": "new.one", "name": "New", "description": "d", "version": 1,
        "definition": {"nodes": [{"id": "n", "type": "value", "config": {}}], "edges": []},
    }])

    db = MagicMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
    db.add = MagicMock()
    db.flush = AsyncMock()

    changed = await presets.load_presets(db)
    assert changed == ["new.one"]
    assert db.add.called
    added = db.add.call_args.args[0]
    assert added.slug == "new.one"
    assert added.is_system is True
    assert added.user_id is None
    assert added.version == 1


@pytest.mark.asyncio
async def test_load_presets_upgrades_when_version_newer(monkeypatch):
    """slug 已存在但 yaml.version > db.version → 升级"""
    existing = SimpleNamespace(
        id=uuid.uuid4(), slug="x", name="old", description="", version=1,
        definition={"nodes": [{"id": "n", "type": "value", "config": {}}], "edges": []},
    )
    monkeypatch.setattr(presets, "_scan_presets", lambda: [{
        "slug": "x", "name": "new", "description": "newer", "version": 2,
        "definition": {"nodes": [{"id": "m", "type": "value", "config": {}}], "edges": []},
    }])

    db = MagicMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: existing))
    db.add = MagicMock()
    db.flush = AsyncMock()

    changed = await presets.load_presets(db)
    assert changed == ["x"]
    assert existing.name == "new"
    assert existing.version == 2
    assert existing.definition == {
        "nodes": [{"id": "m", "type": "value", "config": {}}], "edges": [],
    }


@pytest.mark.asyncio
async def test_load_presets_skips_when_version_equal(monkeypatch):
    """slug 已存在且 version 相同 → 跳过，不计入 changed"""
    existing = SimpleNamespace(
        id=uuid.uuid4(), slug="y", name="same", description="", version=3,
        definition={"nodes": [{"id": "n", "type": "value", "config": {}}], "edges": []},
    )
    monkeypatch.setattr(presets, "_scan_presets", lambda: [{
        "slug": "y", "name": "ignored", "description": "x", "version": 3,
        "definition": {"nodes": [{"id": "z", "type": "value", "config": {}}], "edges": []},
    }])

    db = MagicMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: existing))
    db.add = MagicMock()
    db.flush = AsyncMock()

    changed = await presets.load_presets(db)
    assert changed == []
    # 不应被改动
    assert existing.name == "same"
    assert existing.version == 3


@pytest.mark.asyncio
async def test_load_presets_skips_when_yaml_version_older(monkeypatch):
    """yaml.version < db.version → 不降级"""
    existing = SimpleNamespace(
        id=uuid.uuid4(), slug="z", name="prod", description="", version=5,
        definition={"nodes": [{"id": "n", "type": "value", "config": {}}], "edges": []},
    )
    monkeypatch.setattr(presets, "_scan_presets", lambda: [{
        "slug": "z", "name": "rollback", "description": "", "version": 2,
        "definition": {"nodes": [{"id": "n", "type": "value", "config": {}}], "edges": []},
    }])

    db = MagicMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: existing))
    db.add = MagicMock()
    db.flush = AsyncMock()

    changed = await presets.load_presets(db)
    assert changed == []
    assert existing.name == "prod"
    assert existing.version == 5


# ---------- 实际的 3 个预设文件健全度 ----------


def test_real_preset_files_parse_and_pass_dag_validation():
    """src/openagentic/workflow/presets/*.yaml：每个文件能解析 + DAG 校验通过 + 必备字段齐全。"""
    files = sorted(presets.PRESETS_DIR.glob("*.yaml"))
    assert len(files) >= 3, f"expected at least 3 preset YAMLs, got {[f.name for f in files]}"

    seen_slugs: set[str] = set()
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        # 必备字段
        for field in ("slug", "name", "version", "definition"):
            assert field in data, f"{path.name} missing {field}"
        # slug 唯一
        assert data["slug"] not in seen_slugs, f"duplicate slug {data['slug']} in {path.name}"
        seen_slugs.add(data["slug"])
        # DAG 校验（节点类型、边引用、无环）—— service.validate_definition 是单一事实源
        service.validate_definition(data["definition"])


def test_real_preset_files_use_supported_node_types_only():
    """三个预设里出现的所有 node type 都必须在 validate_definition 的白名单里。"""
    allowed = {"value", "tool", "llm", "approval", "human_input", "feishu", "wecom"}
    for path in sorted(presets.PRESETS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for node in data["definition"]["nodes"]:
            assert node["type"] in allowed, f"{path.name} uses unsupported type {node['type']}"


# ---------- service: SystemWorkflowImmutable 防护 ----------


@pytest.mark.asyncio
async def test_update_workflow_rejects_system_preset():
    """系统预设不可改——服务层抛 SystemWorkflowImmutable。"""
    from openagentic.workflow import schemas

    db = MagicMock()
    db.flush = AsyncMock()
    sys_wf = SimpleNamespace(
        id=uuid.uuid4(), user_id=None, is_system=True, slug="sys.x",
        name="sys", description="", definition={"nodes": [], "edges": []},
        is_active=True, version=1,
    )
    body = schemas.WorkflowUpdate(name="hacked")
    with pytest.raises(service.SystemWorkflowImmutable):
        await service.update_workflow(db, sys_wf, body)


@pytest.mark.asyncio
async def test_delete_workflow_rejects_system_preset():
    """系统预设不可删——服务层抛 SystemWorkflowImmutable。"""
    db = MagicMock()
    db.delete = AsyncMock()
    sys_wf = SimpleNamespace(is_system=True, slug="sys.y")
    with pytest.raises(service.SystemWorkflowImmutable):
        await service.delete_workflow(db, sys_wf)
    assert not db.delete.called


@pytest.mark.asyncio
async def test_fork_workflow_creates_private_copy():
    """fork 出的副本：当前用户拥有 + is_system=False + slug=None。"""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    user_id = uuid.uuid4()
    source = SimpleNamespace(
        id=uuid.uuid4(), user_id=None, is_system=True, slug="sys.z",
        name="origin", description="orig",
        definition={"nodes": [{"id": "n", "type": "value", "config": {}}], "edges": []},
    )
    out = await service.fork_workflow(db, source, user_id)
    assert out.user_id == user_id
    assert out.is_system is False
    assert out.slug is None
    assert out.name.endswith("(fork)")
    assert out.definition == source.definition
