# OpenAgentic

OpenAgentic 是一个开源的 Agent 平台，提供统一的模型配置、对话、工具调用、记忆、知识库、工作流和多入口接入能力。当前仓库包含 FastAPI 服务端、终端 ReAct CLI、React Web UI、Android 客户端、飞书渠道和本地优先个人助手验证原型。

项目仍在快速迭代中。下面的状态以仓库当前代码为准（2026-09-24）；规划中的客户端和能力不会标记为已上线。

| 资源 | 链接 |
| --- | --- |
| 仓库 | [github.com/openagentic-ai/open-agentic](https://github.com/openagentic-ai/open-agentic) |
| 许可证 | [Apache License 2.0](LICENSE) |
| 架构决策 | [docs/ADR-001-multi-adapter-foundation.md](docs/ADR-001-multi-adapter-foundation.md) |
| 个人助手说明 | [docs/personal-agent.md](docs/personal-agent.md) |

## 当前状态

| 部分 | 状态 | 说明 |
| --- | --- | --- |
| FastAPI API | 可用 | 认证、对话、Agent、工作流、知识库、记忆、Skills、任务等路由已装配 |
| PostgreSQL + pgvector | 可用 | Docker Compose 提供 `pgvector/pgvector:pg16`；生产环境使用 Alembic 迁移 |
| 对话 SSE | 可用 | `POST /api/conversations/{id}/messages` 设置 `stream=true` |
| Client Gateway REST | 可用 | `/api/client/sessions` 支持 Android/Web 创建会话、历史和非流式发送 |
| Client Gateway WebSocket | 未完成 | `src/openagentic/gateway/ws.py` 目前只有协议占位，应用暂未挂载 WebSocket 路由 |
| 飞书 | 可用 | `extensions/channels/feishu.py`，可通过 systemd 独立运行 |
| 企业微信 | 骨架 | 验签、解密和路由代码存在，生产消息链路尚未验证 |
| `extensions/adapters/` | 骨架 | 新 Adapter 协议和注册表已建立，现有飞书生产进程仍使用 `extensions/channels/` |
| Web UI | 开发中 | React 页面和 API 客户端存在，端到端实时对话仍需接通真实 Gateway |
| Android | 开发中 | Kotlin/Compose 客户端已迁移到 Gateway REST；默认模型由服务端配置 |
| 本地模型调度器 | 可用 | `extensions/modeld/` 提供显存预检、健康探测和 Xinference 拉起 |
| 钉钉、小程序、iOS、桌面 | 未开始/暂不做 | 见 [docs/plans/todo.md](docs/plans/todo.md) |

## 架构

```text
入口层
├── extensions/channels/   现有飞书/企微渠道
├── extensions/adapters/   新 Adapter 协议（迁移中）
├── ui/                    Web UI
└── extensions/android/    Android 客户端
        │
        ├── HTTP: /api/*、/api/client/*
        └── 未来：WebSocket ReplyEvent 流
        │
应用层 src/openagentic/application/
└── Session / Identity / Intent / ToolRegistry / Orchestrator
        │
领域层
├── agent       LLM 对话和工具循环
├── workflow    DAG 校验、执行、暂停和恢复
├── knowledge   文档、分块、向量检索
├── memory      Core / Episodic / Procedural 记忆
├── skills      SKILL.md 加载和管理
└── tasks       后台任务和调度
        │
基础设施
└── db / llm / concurrency / observability / tools
```

入口层共用应用层编排。应用层通过 `ReplyEvent` 表达 `thinking`、`tool_call`、`tool_result`、`final` 和 `error` 等事件；各客户端负责渲染。当前真正接入生产的是飞书渠道和 Client Gateway REST，流式 WebSocket 仍在实现中。

## 快速启动

### 安装

要求 Python 3.12、Docker 和 Docker Compose。

```bash
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

至少配置一个模型服务和随机的 `JWT_SECRET_KEY`。默认模型、角色模型和并发参数在 [openagentic.yaml](openagentic.yaml) 中配置，环境变量可以覆盖 `.env` 中的值。

### 启动数据库和 API

```bash
docker compose up -d postgres
PYTHONPATH=src .venv/bin/alembic upgrade head
PYTHONPATH=src .venv/bin/uvicorn openagentic.main:app --host 0.0.0.0 --port 8000
```

也可以启动完整 Compose 服务：

```bash
docker compose up -d --build
```

常用地址：

- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`
- 健康检查：`http://localhost:8000/health`
- Prometheus 指标：`http://localhost:8000/metrics`

> `.env.example` 中的 `DATABASE_URL` 面向容器内 API（主机名为 `postgres`）。如果 API 在宿主机运行，请改为本机可访问的 PostgreSQL 地址；Compose 暴露的宿主机端口是 `5433`。

### Web UI

```bash
cd ui
npm install
npm run dev
```

### 飞书渠道（可选）

设置 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 后，可以运行独立 WebSocket 进程：

```bash
PYTHONPATH=src .venv/bin/python scripts/run_feishu_ws.py
```

Linux systemd 模板见 [scripts/openagentic-feishu.service](scripts/openagentic-feishu.service)。

## CLI

```bash
openagentic
# 或
PYTHONPATH=src python -m openagentic.cli
```

CLI 是一个带工具调用的 ReAct 终端，支持模型和 provider 配置、上下文压缩、成本查看、权限策略、git diff/review 和 Skills 管理。使用 `/help` 查看当前版本实际注册的命令；命令集合会随版本变化。

```text
/providers       查看 provider 配置
/model           查看或切换模型
/skills          查看已加载的 Skills
/context         查看当前上下文
/compact         压缩会话上下文
/cost             查看本次会话成本估算
/permissions      查看工具权限策略
/diff             查看 git diff
/review           让模型审查 git diff
```

没有配置 provider 时，CLI 默认会提示配置。CI 或演示可以使用：

```bash
OPENAGENTIC_SKIP_PROVIDER_CHECK=1 openagentic
```

## 本地优先个人助手

这是独立的验证原型，不等同于通用个人 Agent。它从指定的本地 Markdown/TXT 笔记目录读取资料，生成带来源的行动简报，并保存偏好和上次结果。

```bash
PYTHONPATH=src .venv/bin/python scripts/run_personal_demo.py
```

打开 `http://127.0.0.1:8765`。默认连接 `http://127.0.0.1:11434/v1` 的 OpenAI 兼容本地模型，也可以通过 `PERSONAL_MODEL_MODE=api` 配置用户自己的 API。完整边界见 [docs/personal-agent.md](docs/personal-agent.md)。

## HTTP API 概览

除健康检查和模型/provider 读取接口外，大多数业务接口要求 JWT。先注册或登录获取 token：

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"change-this-password"}'
```

主要路由：

| 功能 | 路径 |
| --- | --- |
| 注册、登录、刷新、当前用户 | `/api/auth/*` |
| 对话和消息（含 SSE） | `/api/conversations/*` |
| Client Gateway 会话 REST | `/api/client/sessions/*` |
| Agent 和执行记录 | `/api/agents/*` |
| 工作流、运行、取消、恢复 | `/api/workflows/*`、`/api/workflow-runs/*` |
| 知识库、文档、检索 | `/api/knowledge/*` |
| Core/Episodic/Procedural 记忆 | `/api/memory/*` |
| Skills | `/api/skills/*` |
| 后台任务 | `/api/tasks/*` |
| 渠道配置 | `/api/channels/*` |
| 设备 | `/api/devices/*` |
| 模型和 provider | `/api/models`、`/api/llm/*` |

非流式对话示例：

```bash
curl -X POST http://localhost:8000/api/conversations/{conversation_id}/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"message":"你好","stream":false}'
```

流式对话把 `stream` 设置为 `true`，响应类型为 `text/event-stream`。`/api/client/sessions/{id}/messages` 当前只接受非流式请求；流式 Client Gateway 接口待 WebSocket 实现完成后启用。

## 工作流

工作流定义保存在 `workflows.definition`，当前执行器按拓扑序串行执行。支持：

- `value`：字面量或模板值
- `tool`：调用工具注册表
- `llm`：调用 LiteLLM
- `feishu`、`wecom`：执行相应渠道动作
- `approval`、`human_input`：进入 `suspended` 等待外部输入

模板支持 `{{input.key}}` 和 `{{nodes.node_id}}`。节点支持超时和重试；运行支持取消和恢复，并在 `node_states.trace` 中记录节点状态。系统预设位于 `src/openagentic/workflow/presets/`，应用启动时按 slug/version 同步到数据库，用户需要 fork 后才能修改。

当前未完成的工作流能力包括同层并行、子工作流和完整的渠道审批回调。

## 模型与本地推理

模型角色统一写在 [openagentic.yaml](openagentic.yaml)：`default`、`cli`、`complex`、`evaluator`、`channel`、`embedding` 和 `local`。运行时通过 LiteLLM 使用 OpenAI、Anthropic、DeepSeek、Ollama、Xinference 等兼容 provider。

本地推理默认使用 Xinference 的 OpenAI 兼容地址（`XINFERENCE_API_BASE`）。`extensions/modeld/` 是可选的本地模型生命周期服务，负责显存预检、真实补全健康探测、按需请求 Xinference 拉起模型和可选的周期检查。它只管理模型生命周期，不会终止其他进程。详情见 [extensions/modeld/README.md](extensions/modeld/README.md)。

## 开发与测试

```bash
pip install -e ".[dev]"
PYTHONPATH=src pytest -q
ruff check src tests
mypy src/openagentic
cd ui && npm run build
```

测试默认需要开发依赖；涉及数据库或 API 的测试还需要可用的测试配置。代码结构和提交约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。架构迁移请先阅读 [docs/ADR-001-multi-adapter-foundation.md](docs/ADR-001-multi-adapter-foundation.md)。

## 数据和隐私边界

- 数据库、上传文件和本地记忆由部署者管理；生产环境应更换默认数据库密码和 JWT 密钥。
- 模型请求会把相应的对话、工具输入或知识库内容发送给配置的模型服务。使用第三方 API 前请确认其数据处理条款。
- 本地个人助手会把偏好和结果写入其数据目录；API key 只保存在运行进程中，不写入简报和状态文件。
- 工具执行、文件访问和渠道凭据属于部署者的信任边界，请按实际环境收紧权限、CORS 和网络访问。

## 许可证

本项目采用 Apache License 2.0，详见 [LICENSE](LICENSE)。
