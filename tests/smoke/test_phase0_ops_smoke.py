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


async def _wait_pg_ready(port: int, timeout_s: float = 90.0) -> None:
    """Wait until postgres accepts real connections.

    TCP reachability is not enough: the container's port is bound as soon as it
    starts, while initdb/restart inside keeps rejecting connections for several
    seconds. Retry an actual asyncpg handshake until it succeeds.
    """
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            conn = await asyncpg.connect(
                host="127.0.0.1",
                port=port,
                user="openagentic",
                password="openagentic",
                database="postgres",
                timeout=5,
            )
            await conn.close()
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            await asyncio.sleep(1.0)
    raise TimeoutError(f"postgres not ready on port {port} within {timeout_s}s, last_error={last_error!r}")


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)


def _compose_with_ports(source: Path, pg_port: int, app_port: int | None = None) -> str:
    text = source.read_text(encoding="utf-8")
    text = text.replace('"5433:5432"', f'"{pg_port}:5432"')
    if app_port is not None:
        text = text.replace('"8000:8000"', f'"{app_port}:8000"')
    # Compose 把 build/volume 等相对路径解析到 compose 文件所在目录，
    # 而测试把 compose 写到临时目录，必须把上下文改成项目根目录。
    text = text.replace("build: .", f"build: {source.parent}")
    return text


def _write_smoke_env(tmp: Path) -> None:
    """Write a minimal .env next to the temp compose file.

    The app service declares `env_file: .env`; compose fails when the file is
    missing. An empty file makes the container fall back to Settings defaults
    (DATABASE_URL → compose-network postgres, APP_ENV=development) and avoids
    injecting real FEISHU/LLM credentials into the smoke container.
    """
    (tmp / ".env").write_text("", encoding="utf-8")


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
            await _wait_pg_ready(pg_port)

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
        _write_smoke_env(Path(tmpdir))

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
