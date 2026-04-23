"""Guardrails for knowledge Alembic migration chain and DDL coverage."""

from pathlib import Path


def test_knowledge_migration_links_from_workflow_revision():
    migration_path = Path("alembic/versions/add_knowledge_tables.py")
    text = migration_path.read_text(encoding="utf-8")

    assert 'revision: str = "c3af2e8d41bb"' in text
    assert 'down_revision: Union[str, None] = "9d4f7c21b6aa"' in text


def test_knowledge_migration_contains_pgvector_and_tables():
    migration_path = Path("alembic/versions/add_knowledge_tables.py")
    text = migration_path.read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in text
    assert '"knowledge_documents"' in text
    assert '"knowledge_chunks"' in text
    assert "Vector(1536)" in text
