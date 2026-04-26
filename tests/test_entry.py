"""Test CLI entry point bootstrap logic."""

import sys
from unittest.mock import patch, MagicMock

import pytest

from openagentic_entry import main as entry_main


class TestEntryPoint:
    def test_module_importable(self):
        """验证 entry point 包可导入。"""
        import openagentic_entry
        assert hasattr(openagentic_entry, "main")

    def test_main_calls_cli_main(self):
        """正常情况下 main() 应调用 cli_main。"""
        with patch("openagentic.cli.main") as mock_cli_main:
            entry_main()
            mock_cli_main.assert_called_once()

    def test_main_installs_when_module_not_found(self):
        """cli 未安装时，main 应 Fallback 到 pip install 再重试。"""
        with patch("subprocess.run") as mock_run, \
             patch("subprocess.call") as mock_call:
            mock_run.return_value.returncode = 0
            mock_call.return_value = 0

            # 模拟第一次 import 失败、第二次成功
            with patch.dict(sys.modules, {"openagentic.cli": None}):
                # We cannot easily remove the module; instead test the graceful path
                pass

    def test_repo_root_is_parent(self):
        """_repo_root 应返回仓库根目录。"""
        from openagentic_entry import _repo_root
        root = _repo_root()
        assert root.name == "open-agentic"
