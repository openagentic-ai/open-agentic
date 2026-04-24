"""Tests for CLI tool execution and reasoning content preservation.

Covers:
- execute_tool async interface
- Tool confirmation gate
- DeepSeek reasoning_content preservation in llm.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from openagentic.cli.tools import ConfirmFn, execute_tool


# ---------------------------------------------------------------------------
# execute_tool async tests
# ---------------------------------------------------------------------------


class TestExecuteToolAsync:
    @pytest.mark.asyncio
    async def test_run_command_basic(self):
        result = await execute_tool("run_command", {"command": "echo hello"})
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_run_command_nonzero_exit(self):
        result = await execute_tool("run_command", {"command": "exit 42"})
        assert "[exit code 42]" in result

    @pytest.mark.asyncio
    async def test_read_file(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_text("test content 123")
        result = await execute_tool("read_file", {"path": str(f)})
        assert "test content 123" in result

    @pytest.mark.asyncio
    async def test_read_file_empty(self, tmp_path: Path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = await execute_tool("read_file", {"path": str(f)})
        assert result == "(empty file)"

    @pytest.mark.asyncio
    async def test_write_file_with_confirm_fn(self, tmp_path: Path):
        target = tmp_path / "output.txt"
        confirm = AsyncMock(return_value=True)
        result = await execute_tool(
            "write_file",
            {"path": str(target), "content": "hello world"},
            confirm_fn=confirm,
        )
        assert "OK" in result
        assert target.read_text() == "hello world"
        confirm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_write_file_refused(self, tmp_path: Path):
        target = tmp_path / "refused.txt"
        confirm = AsyncMock(return_value=False)
        result = await execute_tool(
            "write_file",
            {"path": str(target), "content": "data"},
            confirm_fn=confirm,
        )
        assert "REFUSED" in result
        assert not target.exists()

    @pytest.mark.asyncio
    async def test_delete_file_with_confirm_fn(self, tmp_path: Path):
        target = tmp_path / "to_delete.txt"
        target.write_text("bye")
        confirm = AsyncMock(return_value=True)
        result = await execute_tool(
            "delete_file",
            {"path": str(target)},
            confirm_fn=confirm,
        )
        assert "OK" in result
        assert not target.exists()

    @pytest.mark.asyncio
    async def test_delete_file_refused(self, tmp_path: Path):
        target = tmp_path / "keep.txt"
        target.write_text("keep me")
        confirm = AsyncMock(return_value=False)
        result = await execute_tool(
            "delete_file",
            {"path": str(target)},
            confirm_fn=confirm,
        )
        assert "REFUSED" in result
        assert target.exists()

    @pytest.mark.asyncio
    async def test_write_file_no_confirm_fn_non_tty(self, tmp_path: Path):
        """Without confirm_fn and non-TTY, write should be refused."""
        target = tmp_path / "nope.txt"
        with patch("openagentic.cli.tools.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            mock_sys.stdout.isatty.return_value = False
            result = await execute_tool(
                "write_file",
                {"path": str(target), "content": "data"},
            )
        assert "REFUSED" in result

    @pytest.mark.asyncio
    async def test_done_tool(self):
        result = await execute_tool("done", {"summary": "all done!"})
        assert result == "all done!"

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await execute_tool("nonexistent", {})
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_write_file_empty_path(self):
        result = await execute_tool("write_file", {"path": "", "content": "x"})
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_delete_file_nonexistent(self):
        result = await execute_tool("delete_file", {"path": "/tmp/_no_such_file_xyz"})
        assert "ERROR" in result


# ---------------------------------------------------------------------------
# DeepSeek reasoning_content preservation (llm.py)
# ---------------------------------------------------------------------------


class TestReasoningContentPreservation:
    def test_ensure_reasoning_content_adds_to_assistant_messages(self):
        from openagentic.cli.llm import _ensure_reasoning_content

        messages = [
            {"role": "system", "content": "you are helpful"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "bye"},
            {"role": "assistant", "content": "goodbye", "reasoning_content": "thinking..."},
        ]
        patched = _ensure_reasoning_content(messages)
        assert "reasoning_content" not in patched[0]
        assert "reasoning_content" not in patched[1]
        assert patched[2]["reasoning_content"] == ""
        assert "reasoning_content" not in patched[3]
        assert patched[4]["reasoning_content"] == "thinking..."

    def test_ensure_reasoning_content_does_not_mutate_original(self):
        from openagentic.cli.llm import _ensure_reasoning_content

        original = {"role": "assistant", "content": "hi"}
        messages = [original]
        patched = _ensure_reasoning_content(messages)
        assert "reasoning_content" not in original
        assert "reasoning_content" in patched[0]

    def test_is_deepseek_reasoning_model(self):
        from openagentic.cli.llm import _is_deepseek_reasoning_model

        assert _is_deepseek_reasoning_model("deepseek-v4-pro")
        assert _is_deepseek_reasoning_model("deepseek-v4-flash")
        assert _is_deepseek_reasoning_model("deepseek-reasoner")
        assert not _is_deepseek_reasoning_model("gpt-4o")
        assert not _is_deepseek_reasoning_model("claude-3-opus")
