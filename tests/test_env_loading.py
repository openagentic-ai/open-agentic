"""`.env` 必须真的写回 os.environ。

背景：`Settings` 用的是 pydantic 的 `env_file`，它只把值读进 Settings 对象，
**不会**写回进程环境。而控制面 / Jev 这些按「环境变量激活」设计的模块读的是
`os.environ`——不写回就意味着它们**静默不启用**（2026-09-23 实际踩到：
控制面部署完成、测试全绿，但线上根本没激活）。

优先级：已存在的环境变量优先（systemd `EnvironmentFile` 与 CLI 显式传入不该被 .env 覆盖）。
"""

from __future__ import annotations

import os
from pathlib import Path

from openagentic.config import load_env_file


def test_env_file_reaches_os_environ(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAGENTIC_TEST_MARKER=hello\n", encoding="utf-8")
    monkeypatch.delenv("OPENAGENTIC_TEST_MARKER", raising=False)

    load_env_file(env_file)

    assert os.environ.get("OPENAGENTIC_TEST_MARKER") == "hello"


def test_existing_env_wins(tmp_path: Path, monkeypatch):
    """已存在的环境变量优先——systemd/cli 传进来的不该被 .env 覆盖。"""
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAGENTIC_TEST_MARKER=from_file\n", encoding="utf-8")
    monkeypatch.setenv("OPENAGENTIC_TEST_MARKER", "from_env")

    load_env_file(env_file)

    assert os.environ.get("OPENAGENTIC_TEST_MARKER") == "from_env"


def test_missing_file_is_silent(tmp_path: Path):
    """文件不存在不能炸——测试/CI 环境常常没有 .env。"""
    load_env_file(tmp_path / "nope.env")
