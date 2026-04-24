"""Phase 0 ops smoke tests: real Alembic migration + Docker health."""

from __future__ import annotations

import asyncio
from contextlib import closing
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid

import asyncpg
import httpx
import pytest


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _has_docker_compose() -> bool:
    return shutil.which("docker") is not None


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


def _wait_tcp(host: str, port: int, timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                return
        except OSError:
            time.sleep(1.0)
    raise TimeoutError(f"TCP {host}:{port} not ready within {timeout_s}s")


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)


def _compose_with_ports(source: Path, pg_port: int, app_port: int | None = None) -> str:
    text = source.read_text(encoding="utf-8")
    text = text.replace('"5433:5432"', f'"{pg_port}:5432"')
    if app_port is not None:
        text = text.replace('"8000:8000"', f'"{app_port}:8000"')
    return text


@pytest.mark.asyncio
async def test_alembic_upgrade_head_smoke_real_db():
    """Run `alembic upgrade head` against a real temporary PostgreSQL DB."""
    if not _has_docker_compose():
        pytest.skip("docker unavailable in current environment")

    root = _project_root()
    compose_src = root / "docker-compose.yml"
    pg_port = _free_port()
    project_name = f"oa-smoke-mig-{uuid.uuid4().hex[:8]}"
    db_name = f"openagentic_smoke_{uuid.uuid4().hex[:8]}"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        compose_file = tmp / "compose.yml"
        compose_file.write_text(_compose_with_ports(compose_src, pg_port=pg_port), encoding="utf-8")

        up = _run(
            ["docker", "compose", "-f", str(compose_file), "-p", project_name, "up", "-d", "postgres"],
            cwd=root,
        )
        if up.returncode != 0:
            raise AssertionError(f"docker compose up postgres failed:\n{up.stderr}\n{up.stdout}")

        try:
            _wait_tcp("127.0.0.1", pg_port, timeout_s=90.0)

            admin = await asyncpg.connect(
                host="127.0.0.1",
                port=pg_port,
                user="openagentic",
                password="openagentic",
                database="postgres",
            )
            try:
                await admin.execute(f'CREATE DATABASE "{db_name}"')
            finally:
                await admin.close()

            ini_text = (root / "alembic.ini").read_text(encoding="utf-8")
            smoke_url = (
                f"postgresql+asyncpg://openagentic:openagentic@127.0.0.1:{pg_port}/{db_name}"
            )
            ini_text = ini_text.replace(
                "sqlalchemy.url = postgresql+asyncpg://openagentic:openagentic@localhost:5433/openagentic",
                f"sqlalchemy.url = {smoke_url}",
            )
            ini_file = tmp / "alembic-smoke.ini"
            ini_file.write_text(ini_text, encoding="utf-8")

            migrate = _run([sys.executable, "-m", "alembic", "-c", str(ini_file), "upgrade", "head"], cwd=root)
            if migrate.returncode != 0:
                raise AssertionError(f"alembic upgrade head failed:\n{migrate.stderr}\n{migrate.stdout}")

            conn = await asyncpg.connect(
                host="127.0.0.1",
                port=pg_port,
                user="openagentic",
                password="openagentic",
                database=db_name,
            )
            try:
                for table in ("users", "conversations", "agents", "workflows", "knowledge_chunks"):
                    exists = await conn.fetchval(
                        "select to_regclass($1) is not null",
                        f"public.{table}",
                    )
                    assert exists, f"expected migrated table missing: {table}"
            finally:
                await conn.close()
        finally:
            # Best effort cleanup.
            try:
                admin = await asyncpg.connect(
                    host="127.0.0.1",
                    port=pg_port,
                    user="openagentic",
                    password="openagentic",
                    database="postgres",
                )
                await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
                await admin.close()
            except Exception:
                pass

            _run(["docker", "compose", "-f", str(compose_file), "-p", project_name, "down", "-v"], cwd=root)


def test_docker_compose_health_smoke():
    """Bring up Docker Compose app+postgres and assert `/health` responds."""
    if not _has_docker_compose():
        pytest.skip("docker unavailable in current environment")

    root = _project_root()
    compose_src = root / "docker-compose.yml"
    pg_port = _free_port()
    app_port = _free_port()
    project_name = f"oa-smoke-health-{uuid.uuid4().hex[:8]}"

    with tempfile.TemporaryDirectory() as tmpdir:
        compose_file = Path(tmpdir) / "compose.yml"
        compose_file.write_text(
            _compose_with_ports(compose_src, pg_port=pg_port, app_port=app_port),
            encoding="utf-8",
        )

        up = _run(
            ["docker", "compose", "-f", str(compose_file), "-p", project_name, "up", "-d", "postgres", "app"],
            cwd=root,
        )
        if up.returncode != 0:
            raise AssertionError(f"docker compose up app/postgres failed:\n{up.stderr}\n{up.stdout}")

        try:
            deadline = time.time() + 180.0
            last_error: Exception | None = None
            while time.time() < deadline:
                try:
                    resp = httpx.get(f"http://127.0.0.1:{app_port}/health", timeout=2.0)
                    if resp.status_code == 200:
                        payload = resp.json()
                        assert payload.get("status") == "ok"
                        return
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                time.sleep(2.0)
            raise AssertionError(f"/health not ready on port {app_port}, last_error={last_error!r}")
        finally:
            _run(["docker", "compose", "-f", str(compose_file), "-p", project_name, "down", "-v"], cwd=root)
