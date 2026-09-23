from pathlib import Path

import pytest

from openagentic.workspace import PersonalWorkspace


def test_workspace_is_user_scoped(tmp_path: Path):
    workspace = PersonalWorkspace.for_user(tmp_path, "alice")
    assert workspace.root == tmp_path / "users" / "alice"
    assert workspace.path("notes/today.md").parent == workspace.root / "notes"
    with pytest.raises(ValueError):
        workspace.path("../../secret")
