from pathlib import Path

from openagentic.memory.manager import MemoryManager


def test_user_scoped_memory_isolated_and_persistent(tmp_path: Path):
    alice = MemoryManager(tmp_path, user_id="alice")
    bob = MemoryManager(tmp_path, user_id="bob")

    alice.save_core_memory("language", "中文", "preference")
    bob.save_core_memory("language", "English", "preference")

    assert [x.value for x in alice.list_core()] == ["中文"]
    assert [x.value for x in bob.list_core()] == ["English"]
    assert (tmp_path / "users" / "alice" / "core" / "preference").is_dir()

    restarted = MemoryManager(tmp_path, user_id="alice")
    assert restarted.list_core()[0].value == "中文"


def test_user_id_cannot_escape_memory_root(tmp_path: Path):
    manager = MemoryManager(tmp_path, user_id="../../outside")
    manager.save_core_memory("safe", "value", "reference")
    assert (tmp_path / "users" / ".._.._outside").exists()
    assert not (tmp_path / "outside").exists()
