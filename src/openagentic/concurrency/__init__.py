"""模块说明（中文）：`src/openagentic/concurrency/`。

并发治理底座 —— 与所有应用（渠道/HTTP/Workflow/未来钉钉/SaaS/桌面客户端）解耦。

设计原则（遵循 #3 解耦第一原则）：
1. 环境变量激活：`OPENAGENTIC_GATE_*` 可选，未配置走默认值（100 量级）
2. 抽象接口定义契约：只暴露 `ConcurrencyGate.submit()` 和 `acquire()`
3. 回调注入不硬编码：调用方传 coro_factory，底座不知道下游是 LLM 还是飞书
4. 独立加载失败隔离：本模块只 import 标准库 + structlog，不 import 任何业务模块
5. main.py 只一行接入：`from openagentic.concurrency import get_default_gate`

并发模型（针对 100 量级单机部署）：
- 全局信号量：上限 100，所有提交都过这一关
- 类别信号量：llm/subprocess/io 各自独立配额
- 令牌桶限流：每个类别可选 rate_per_sec（保护下游 provider）
- 会话锁：同 session_key 严格串行，避免同会话历史竞态
- 排队上限：超过则立即抛 GateBusy，不无限等待

接入示例：

    from openagentic.concurrency import get_default_gate

    gate = get_default_gate()
    reply = await gate.submit(
        session_key=chat_id,                    # 同会话串行
        coro_factory=lambda: ai.reply(text),    # 工厂函数（排队后才创建协程）
        category="llm",                         # 走 LLM 类别配额
        timeout=180.0,
    )

未来接入钉钉/SaaS/Office 插件，只需在新渠道里调 `gate.submit(...)`，不动底座。
"""

from openagentic.concurrency.gate import (
    ConcurrencyGate,
    GateBusy,
    GateTimeout,
    get_default_gate,
    reset_default_gate,
)

__all__ = [
    "ConcurrencyGate",
    "GateBusy",
    "GateTimeout",
    "get_default_gate",
    "reset_default_gate",
]
