"""模块说明（中文）：`src/openagentic/cli/llm.py`。

向后兼容封装——实际逻辑已迁移至 `openagentic.agent.llm`。
CLI 入口仍然从此文件导入，行为不变。
"""

from openagentic.agent.llm import (  # noqa: F401
    is_deepseek_reasoning_model,
    ensure_reasoning_content,
    litellm_chat,
)

# 向后兼容别名
_is_deepseek_reasoning_model = is_deepseek_reasoning_model
_ensure_reasoning_content = ensure_reasoning_content
