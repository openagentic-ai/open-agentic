"""模块说明（中文）：`src/openagentic/cli/entry.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

from __future__ import annotations

import argparse
import asyncio

from dotenv import load_dotenv

from openagentic.cli.auth import platform_authenticate_sync
from openagentic.cli.bootstrap import maybe_auto_install_editable
from openagentic.cli.platform_adapter import CLI_PLATFORM
from openagentic.cli.providers import DEFAULT_MODEL
from openagentic.cli.repl import main_loop
from openagentic.config import SETTINGS

load_dotenv()


def main() -> None:
    maybe_auto_install_editable()
    CLI_PLATFORM.configure_event_loop_policy()
    CLI_PLATFORM.ensure_line_input_mode()
    parser = argparse.ArgumentParser(description="OpenAgentic Agent CLI (ReAct)")
    parser.add_argument(
        "-m",
        "--model",
        default=DEFAULT_MODEL,
        help=(
            f"Model name (default: {DEFAULT_MODEL}; "
            "OpenAI mode uses OPENAI_CHAT_MODEL when unchanged)"
        ),
    )
    parser.add_argument(
        "--provider",
        default="auto",
        help=(
            "LLM provider id "
            "(auto/openai/anthropic/xai/gemini/deepseek/mistral/cohere/groq/openrouter/"
            "moonshot/zhipu/minimax/volcengine/baidu/tencent/nvidia/together/fireworks/qwen/ollama)"
        ),
    )
    parser.add_argument("-s", "--system", default=None, help="Custom system prompt")
    parser.add_argument(
        "--api-base",
        default=SETTINGS.OPENAGENTIC_API_BASE or None,
        metavar="URL",
        help="OpenAgentic 服务根地址（如 http://127.0.0.1:8000）；若设置则启动前必须登录或注册以获取 JWT",
    )
    parser.add_argument(
        "--require-auth",
        action="store_true",
        help="启动前必须完成平台登录/注册；未指定 --api-base 时默认 http://127.0.0.1:8000",
    )
    args = parser.parse_args()

    api_base = (args.api_base or "").strip() or None
    if args.require_auth and not api_base:
        api_base = "http://127.0.0.1:8000"

    platform_token: str | None = None
    platform_email: str | None = None
    if api_base:
        platform_token, platform_email = platform_authenticate_sync(api_base)

    try:
        asyncio.run(
            main_loop(
                args.model,
                args.provider,
                args.system,
                platform_api_base=api_base,
                platform_user_email=platform_email,
                platform_access_token=platform_token,
            )
        )
    except KeyboardInterrupt:
        print("\nBye!")
