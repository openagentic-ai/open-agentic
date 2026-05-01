"""Workflow 工具测试：channel_runner 的 execute_tool 分发 + 4 个新工具 +
_resolve_workflow + _build_preset_hint + 基础工具覆盖。

mock async_session + wf_service 层，与 test_presets.py 风格一致。
"""

from __future__ import annotations

import uuid
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from extensions.channels.channel_runner import (
    execute_tool,
    _get_workflow,
    _update_workflow,
    _fork_workflow,
    _delete_workflow,
    _resolve_workflow,
    _save_memory,
    _run_command,
    _read_file,
    _run_lark_cli,
    _current_user_id,
    _current_platform,
    _current_sender_open_id,
    _current_chat_id,
    _build_preset_hint,
    BASE_TOOLS,
    WORKFLOW_TOOLS,
    LARK_TOOL,
)

# ── 工具定义结构验证 ────────────────────────────────────────────────────


class TestToolDefinitions:
    def test_base_tools_count(self):
        assert len(BASE_TOOLS) == 3
        names = [t["function"]["name"] for t in BASE_TOOLS]
        assert "save_memory" in names
        assert "run_command" in names
        assert "read_file" in names

    def test_workflow_tools_count(self):
        assert len(WORKFLOW_TOOLS) == 8
        names = [t["function"]["name"] for t in WORKFLOW_TOOLS]
        for expected in ["list_workflows", "create_workflow", "run_workflow",
                          "query_workflow_run", "get_workflow", "update_workflow",
                          "fork_workflow", "delete_workflow"]:
            assert expected in names, f"missing {expected}"

    def test_lark_tool_has_required_params(self):
        assert LARK_TOOL["function"]["name"] == "lark_cli"
        required = LARK_TOOL["function"]["parameters"]["required"]
        assert "args" in required

    def test_all_tool_definitions_are_valid_function_type(self):
        for tool in BASE_TOOLS + WORKFLOW_TOOLS + [LARK_TOOL]:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]


# ── execute_tool 分发器 ─────────────────────────────────────────────────


class TestExecuteToolDispatch:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        result = await execute_tool("nonexistent_tool", {})
        assert "未知工具" in result

    @pytest.mark.asyncio
    async def test_each_known_tool_responds_without_crash(self, monkeypatch):
        """每个已知工具在被调时不应抛未捕获异常（即使因无身份/无 DB 返回错误）。"""
        # mock _current_user_id 避免实际 DB 查询
        async def mock_user_id():
            return uuid.uuid4()
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id", mock_user_id
        )

        tool_names = [t["function"]["name"] for t in WORKFLOW_TOOLS]

        for name in tool_names:
            try:
                result = await execute_tool(name, {})
                assert isinstance(result, str)
                assert len(result) > 0
            except Exception as e:
                pytest.fail(f"{name} raised {type(e).__name__}: {e}")


# ── _get_workflow ────────────────────────────────────────────────────────


class TestGetWorkflow:
    @pytest.mark.asyncio
    async def test_not_found(self, monkeypatch):
        """找不到 workflow 返回中文错误。"""
        user_id = uuid.uuid4()
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=user_id),
        )
        # mock async_session → db（注意：channel_runner 在函数内部
        # from openagentic.db.session import async_session，所以 monkeypatch 到源头）
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: None)
        )
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "openagentic.db.session.async_session",
            MagicMock(return_value=mock_session),
        )

        result = await _get_workflow(str(uuid.uuid4()))
        assert "错误" in result or "找不到" in result

    @pytest.mark.asyncio
    async def test_empty_workflow_id(self, monkeypatch):
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=uuid.uuid4()),
        )
        result = await _get_workflow("")
        assert "缺少" in result

    @pytest.mark.asyncio
    async def test_no_user(self, monkeypatch):
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=None),
        )
        result = await _get_workflow("any-id")
        assert "未能识别" in result


# ── _update_workflow ─────────────────────────────────────────────────────


class TestUpdateWorkflow:
    @pytest.mark.asyncio
    async def test_no_fields_to_update(self, monkeypatch):
        """未传任何更新字段时返回提示。"""
        user_id = uuid.uuid4()
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=user_id),
        )
        # mock async_session —— update_kwargs 检查在 DB 查询之后
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            return_value=SimpleNamespace(
                scalar_one_or_none=lambda: SimpleNamespace(
                    id=uuid.uuid4(), name="test", is_system=False,
                )
            )
        )
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "openagentic.db.session.async_session",
            MagicMock(return_value=mock_session),
        )

        result = await _update_workflow(str(uuid.uuid4()), None, None, None, None)
        assert "未提供" in result

    @pytest.mark.asyncio
    async def test_no_user(self, monkeypatch):
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=None),
        )
        result = await _update_workflow("any-id", "test", None, None, None)
        assert "未能识别" in result

    @pytest.mark.asyncio
    async def test_empty_workflow_id(self, monkeypatch):
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=uuid.uuid4()),
        )
        result = await _update_workflow("", "test", None, None, None)
        assert "缺少" in result


# ── _fork_workflow ───────────────────────────────────────────────────────


class TestForkWorkflow:
    @pytest.mark.asyncio
    async def test_no_user(self, monkeypatch):
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=None),
        )
        result = await _fork_workflow("any-id", None)
        assert "未能识别" in result

    @pytest.mark.asyncio
    async def test_empty_workflow_id(self, monkeypatch):
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=uuid.uuid4()),
        )
        result = await _fork_workflow("", None)
        assert "缺少" in result


# ── _delete_workflow ─────────────────────────────────────────────────────


class TestDeleteWorkflow:
    @pytest.mark.asyncio
    async def test_no_user(self, monkeypatch):
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=None),
        )
        result = await _delete_workflow("any-id")
        assert "未能识别" in result

    @pytest.mark.asyncio
    async def test_empty_workflow_id(self, monkeypatch):
        monkeypatch.setattr(
            "extensions.channels.channel_runner._current_user_id",
            AsyncMock(return_value=uuid.uuid4()),
        )
        result = await _delete_workflow("")
        assert "缺少" in result


# ── _resolve_workflow ────────────────────────────────────────────────────


class TestResolveWorkflow:
    @pytest.mark.asyncio
    async def test_by_uuid_found(self, monkeypatch):
        user_id = uuid.uuid4()
        wf_id = uuid.uuid4()
        expected_wf = SimpleNamespace(id=wf_id, name="test", is_system=False, user_id=user_id)

        async def mock_get_workflow(db, wid, uid):
            return expected_wf

        monkeypatch.setattr(
            "openagentic.workflow.service.get_workflow", mock_get_workflow
        )
        from extensions.channels.channel_runner import _resolve_workflow
        result = await _resolve_workflow(MagicMock(), str(wf_id), user_id)
        assert result is expected_wf

    @pytest.mark.asyncio
    async def test_by_slug_found(self, monkeypatch):
        user_id = uuid.uuid4()
        expected_wf = SimpleNamespace(id=uuid.uuid4(), name="preset", is_system=True)
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: expected_wf)
        )
        from extensions.channels.channel_runner import _resolve_workflow
        result = await _resolve_workflow(mock_db, "news.tech_weekly", user_id)
        assert result is expected_wf

    @pytest.mark.asyncio
    async def test_not_found(self, monkeypatch):
        user_id = uuid.uuid4()
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: None)
        )
        from extensions.channels.channel_runner import _resolve_workflow
        result = await _resolve_workflow(mock_db, "nonexistent.slug", user_id)
        assert result is None


# ── _build_preset_hint ───────────────────────────────────────────────────


class TestBuildPresetHint:
    def test_with_presets(self, monkeypatch):
        monkeypatch.setattr(
            "openagentic.workflow.presets._scan_presets",
            lambda: [{
                "slug": "news.weekly", "name": "新闻周报",
                "description": "weekly news", "version": 1,
                "definition": {"nodes": [{"id": "n", "type": "value", "config": {}}], "edges": []},
            }],
        )
        hint = _build_preset_hint()
        assert "news.weekly" in hint
        assert "run_workflow" in hint

    def test_empty_presets(self, monkeypatch):
        monkeypatch.setattr(
            "openagentic.workflow.presets._scan_presets", lambda: []
        )
        hint = _build_preset_hint()
        assert hint == ""

    def test_scan_error(self, monkeypatch):
        def raise_err():
            raise RuntimeError("boom")
        monkeypatch.setattr(
            "openagentic.workflow.presets._scan_presets", raise_err
        )
        hint = _build_preset_hint()
        assert hint == ""


# ── _current_user_id ─────────────────────────────────────────────────────


class TestCurrentUserId:
    @pytest.mark.asyncio
    async def test_resolved(self, monkeypatch):
        expected_id = uuid.uuid4()
        async def mock_resolve(platform, sender_open_id):
            return expected_id
        monkeypatch.setattr(
            "openagentic.channels.bindings.resolve_user_id_with_fallback",
            mock_resolve,
        )
        result = await _current_user_id()
        assert result == expected_id

    @pytest.mark.asyncio
    async def test_not_found(self, monkeypatch):
        async def mock_resolve(platform, sender_open_id):
            return None
        monkeypatch.setattr(
            "openagentic.channels.bindings.resolve_user_id_with_fallback",
            mock_resolve,
        )
        result = await _current_user_id()
        assert result is None


# ── _save_memory ─────────────────────────────────────────────────────────


class TestSaveMemory:
    @pytest.mark.asyncio
    async def test_empty_title_returns_error(self):
        result = await _save_memory("", "content", "reference", 0.7)
        assert "错误" in result

    @pytest.mark.asyncio
    async def test_empty_content_returns_error(self):
        result = await _save_memory("title", "", "reference", 0.7)
        assert "错误" in result


# ── _run_command ─────────────────────────────────────────────────────────


class TestRunCommand:
    @pytest.mark.asyncio
    async def test_empty_command_returns_error(self):
        result = await _run_command("")
        assert "错误" in result

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_error(self):
        result = await _run_command("   ")
        assert "错误" in result


# ── _read_file ───────────────────────────────────────────────────────────


class TestReadFile:
    @pytest.mark.asyncio
    async def test_file_not_found(self):
        result = await _read_file("/nonexistent/path/12345.txt")
        assert "不存在" in result

    @pytest.mark.asyncio
    async def test_dangerous_path(self):
        result = await _read_file("/etc/shadow")
        assert "安全" in result


# ── _run_lark_cli ────────────────────────────────────────────────────────


class TestLarkCli:
    @pytest.mark.asyncio
    async def test_not_installed(self, monkeypatch):
        """lark-cli 未安装时返回提示。"""
        async def mock_create(*args, **kwargs):
            raise FileNotFoundError("lark-cli")
        monkeypatch.setattr("asyncio.create_subprocess_exec", mock_create)
        result = await _run_lark_cli(["im", "send"])
        assert "未安装" in result
