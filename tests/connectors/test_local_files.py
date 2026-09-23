from pathlib import Path

import pytest

from openagentic.connectors import ConnectorKind, LocalFileConnector


@pytest.mark.asyncio
async def test_local_file_connector_lists_only_workspace_files(tmp_path: Path):
    (tmp_path / "notes.md").write_text("hello", encoding="utf-8")
    (tmp_path / "photo.png").write_bytes(b"png")
    items = await LocalFileConnector(tmp_path).list("note")
    assert [item.id for item in items] == ["notes.md"]
    assert items[0].kind is ConnectorKind.FILES
