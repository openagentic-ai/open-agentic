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
- **前端**：React 19 + Vite + TailwindCSS + Zustand（通用 Agent UI 仍需对齐后端，商家/预约/记忆页面已接真实 API）
- **DB**：PostgreSQL 16 + pgvector（Docker）
- **迁移**：Alembic（以 Alembic head 为准）
- **CLI 入口**：`python -m openagentic.cli`
- **LLM 网关**：LiteLLM 统一对接 20 个 provider
- **测试**：以当前 CI 结果为准，不维护固定数量

## Phase 路线图

2026-10-03 起，当前产品定位与优先级以 [产品策略](docs/product-strategy.md) 和 [商业平台实施计划](docs/plans/commerce-platform.md) 为准。历史个人助手清单和 ADR 中的产品定位、端建设 P0 与排期不作为当前主线依据。

- **商业目标**：AI 版本的阿里巴巴，连接用户 Agent、SaaS 平台和商家，建立服务发现与真实交易闭环。
- **启动方式**：第一批商家靠地推，客户先通过商家的二维码、客户群和分享链接进入；在一个区域、一个行业验证后再复制。
- **当前 P0**：商家组织与隔离、服务发布、用户确认预约、商家接单履约、订单状态查询，以及最小商家与运营界面。
- **商业验证**：能否接触真实经营流程；能否带来订单或降低接单与服务成本；用户是否再次使用；减少创始人介入后效果是否持续。
- **工程原则**：复用现有 Agent、模型、数据库、任务和工作流底座，分批新增商业领域；订单与个人任务分开，商业能力未验收不得标记上线。

现有后端底座与飞书渠道可复用，其他端的实际状态见 README。商家组织、服务目录与最小预约履约代码已实现，Agent 商业工具、报价、授权与运营/售后已通过本地验证；可预约时段、真实 SaaS 与支付结算待验证；工作流及客户端扩展按对商业试点的必要性排序。

## 三个版本商业代码与记忆（2026-10-03）

- 商家开通、资料编辑、服务草稿/发布/下架、公开店铺与预约申请/接单/完成已通过本地验证，见 [商家工作台说明](docs/merchant-workspace.md)。
- 前端入口：`/merchants`、`/stores/:merchantId`、`/stores/:merchantId/book/:serviceId`、`/orders`、`/memories`。本地离线预览脚本：`scripts/run_merchant_demo.py`，使用独立 SQLite，监听 `127.0.0.1:8766`。
- 第四层仍是程序性记忆，接入 Obsidian 兼容 Vault；服务器 REST 与 DefaultOrchestrator 按用户 UUID 隔离。配置和边界见 [Obsidian 记忆说明](docs/obsidian-memory.md)。旧 channel_runner 的共享记忆与商家团队记忆迁移尚未完成。
- 底座与应用层必须分开：商业 UI 在 `ui/src/apps/commerce/`，应用装配在 `src/openagentic/apps/commerce.py`；底座模块不得反向导入商业模块，架构测试负责检查，见 [架构约束](docs/commerce-architecture.md)。
- V0.2 已实现 Agent 工具、限时报价、明确确认、授权/审计、离线二维码和目录导入；V1.0 本地候选版包含运营记录、模拟费率账单/支付退款、售后与投递重试。严禁把模拟交易写成真实收入或上线验收。
- 新入口：`/agent-commerce`、`/quotes/:id`、`/connections`、`/operations`。标准 API 默认支付关闭，本地示例显式启用模拟支付。
- 商业数据库迁移：`51b4d9e20a71`（商家与服务）、`7c40e13a92bf`（预约订单）、`b27a51f0c842`（开放商业应用）。已验证离线 PostgreSQL SQL 生成，尚未执行真实 PostgreSQL 迁移。

## 渠道和客户端真实状态（2026-09-24 复核）
- **飞书 Bot**：已上线运行，systemd 管理，复用 ConversationEngine。
- **企微 Bot**：代码骨架，`wecom-cli` 不存在，从未跑通端到端流程。
- **钉钉**：尚未开始接入。
- **Web UI**：React/Vite 工程和页面已存在，但当前是假 Telegram/Discord 列表，`useWebSocket` 尚未连通后端。
- **本地推理**：当前后端使用 Xinference + vLLM。
- **Android**：Kotlin/Compose 客户端通过 OpenAgentic Gateway 认证、创建会话并调用 Agent；本地推理走 Xinference + vLLM。
- **推理协议**：产品统一使用 OpenAI-compatible API；Ollama 仅作为开发适配器。

## 15 服部署
- **唯一正本**：`/opt/open-agentic/`
- **飞书 bot**：systemd `openagentic-feishu.service`
- **HTTP API**：uvicorn `0.0.0.0:8000`
- **重启**：`systemctl restart openagentic-feishu.service`
- **SSH**：`ssh root@192.168.0.15`

## 架构精简计划（2026-04）
砍 device/canvas/voice，补工作流/RAG/MCP/多租户。

## 已知待做

待办排序以 [商业平台实施计划](docs/plans/commerce-platform.md) 为准。历史底座待办在安排前应核对当前代码状态，只将支撑试点闭环的事项纳入商业 P0。
