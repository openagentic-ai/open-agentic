from pathlib import Path

import pytest

from openagentic.memory.manager import MemoryManager
from openagentic.memory.obsidian import ObsidianVault
from openagentic.retrieval.prepare import prepare_context


def test_properties_wikilinks_and_backlinks(tmp_path):
    vault = ObsidianVault(tmp_path)
    vault.write("procedures/接单.md", {"name": "接单: 标准", "type": "procedure"}, "确认 [[履约]]。")
    vault.write("procedures/履约.md", {"name": "履约"}, "完成服务")
    note = vault.read("procedures/接单.md")
    assert note["properties"]["name"] == "接单: 标准"
    assert note["links"] == ["履约"]
    assert vault.backlinks("procedures/履约.md") == [{"path": "procedures/接单.md", "name": "接单: 标准"}]
    assert vault.search("标准")[0]["path"] == "procedures/接单.md"
    assert vault.uri("procedures/接单.md").startswith("obsidian://open?path=")


def test_vault_rejects_traversal_symlinks_and_private_directories(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    outside = tmp_path / "private.md"
    outside.write_text("private data")
    (root / "escape.md").symlink_to(outside)
    vault = ObsidianVault(root)
    for path in ("../private.md", str(outside), "escape.md", ".obsidian/private.md", "test.txt"):
        with pytest.raises(ValueError):
            vault.read(path)
    assert vault.search("private") == []


@pytest.mark.asyncio
async def test_fourth_layer_reads_obsidian_edits_in_agent_retrieval(tmp_path):
    mgr = MemoryManager(base_dir=tmp_path / "memory", vault_dir=tmp_path / "vault")
    mgr.save_procedure("接单流程", "接单经验", "接单", ["确认客户需求"])
    note_path = mgr.vault.paths("procedures")[0]
    Path(mgr.vault.root / note_path).write_text(
        "---\nname: 接单流程\ntype: procedure\n---\n接单时先检查可用时间。", encoding="utf-8",
    )
    context = await prepare_context("接单", memory=mgr, route_enabled=False, sufficiency_enabled=False)
    assert "检查可用时间" in context
    assert "可复用流程" in context


def test_different_procedure_names_do_not_overwrite(tmp_path):
    mgr = MemoryManager(base_dir=tmp_path)
    first = mgr.save_procedure("接单:确认", "一", "", ["步骤一"])
    second = mgr.save_procedure("接单/确认", "二", "", ["步骤二"])
    assert first != second
    assert len(mgr.search_procedures("接单", 10)) == 2
