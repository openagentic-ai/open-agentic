# OpenAgentic 项目规则 & 记忆

## 飞书回复格式
禁止在飞书回复中使用表格和代码块。用 prompt 约束格式，不做 sanitize 兜底。

## 基本信息
- **Mac 开发路径**：`~/open-agentic/`
- **15 服部署路径**：`/opt/open-agentic/`（飞书 Bot + FastAPI 常驻；企微目前未跑通）
- **GitHub**：openagentic-ai/open-agentic
- **官网**：https://openagentic-ai.github.io/
- **License**：Apache 2.0

## 技术栈
- **后端**：Python 3.12 + FastAPI + SQLAlchemy(async) + pydantic-settings
- **前端**：React 19 + Vite + TailwindCSS + Zustand（当前 UI 仍是未打通后端的原型）
- **DB**：PostgreSQL 16 + pgvector（Docker）
- **迁移**：Alembic（7 个 revision）
- **CLI 入口**：`python -m openagentic.cli`
- **LLM 网关**：LiteLLM 统一对接 20 个 provider
- **测试**：以当前 CI 结果为准，不维护固定数量

## Phase 路线图
后端底座和飞书 Bot 已落地；Web、Android、企微、钉钉尚未完成端到端接入；Phase 7 Workflow 扩展进行中。

## 渠道和客户端真实状态（2026-09-24 复核）
- **飞书 Bot**：已上线运行，systemd 管理，复用 ConversationEngine。
- **企微 Bot**：代码骨架，`wecom-cli` 不存在，从未跑通端到端流程。
- **钉钉**：尚未开始接入。
- **Web UI**：React/Vite 工程和页面已存在，但当前是假 Telegram/Discord 列表，`useWebSocket` 尚未连通后端。
- **本地推理**：当前后端使用 Xinference + vLLM。
- **Android**：Kotlin/Compose 工程已存在；客户端代码仍请求旧 Ollama API，尚未接入当前推理链路和 Agent。

## 15 服部署
- **唯一正本**：`/opt/open-agentic/`
- **飞书 bot**：systemd `openagentic-feishu.service`
- **HTTP API**：uvicorn `0.0.0.0:8000`
- **重启**：`systemctl restart openagentic-feishu.service`
- **SSH**：`ssh root@192.168.0.15`

## 架构精简计划（2026-04）
砍 device/canvas/voice，补工作流/RAG/MCP/多租户。

## 已知待做
- Workflow resume 接口 / 事件触发器
- 四层记忆 → pgvector 语义检索升级
