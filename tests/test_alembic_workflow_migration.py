"""Guardrails for workflow Alembic migration chain and DDL coverage."""

from pathlib import Path


def test_workflow_migration_links_from_initial_revision():
    migration_path = Path("alembic/versions/add_workflow_tables.py")
    text = migration_path.read_text(encoding="utf-8")

    assert 'revision: str = "9d4f7c21b6aa"' in text
    assert 'down_revision: Union[str, None] = "62da57f49c3e"' in text


def test_workflow_migration_contains_required_tables_and_indexes():
    migration_path = Path("alembic/versions/add_workflow_tables.py")
    text = migration_path.read_text(encoding="utf-8")

    assert "op.create_table(" in text
    assert '"workflows"' in text
    assert '"workflow_runs"' in text
    assert 'ix_workflows_user_id' in text
    assert 'ix_workflow_runs_workflow_id' in text
    assert 'ix_workflow_runs_user_id' in text
    assert 'name="workflowrunstatus"' in text
