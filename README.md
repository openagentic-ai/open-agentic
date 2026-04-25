# OpenAgentic

企业级 AI Agent 平台 — Python (FastAPI) + React，面向私有化部署。多模型对话、Agent 工具编排、RAG 知识库、工作流引擎、四层记忆系统。

| 资源 | 链接 |
|------|------|
| 官网 | [openagentic-ai.github.io](https://openagentic-ai.github.io) |
| 仓库 | [github.com/openagentic-ai/open-agentic](https://github.com/openagentic-ai/open-agentic) |
| 许可证 | MIT |

## 目录

- [实现进度](#实现进度)
- [快速启动](#快速启动)
- [CLI 模式](#cli-模式)
- [API 端点](#api-端点)
- [架构](#架构)
- [路线图](#路线图)
- [开发与测试](#开发与测试)
- [常见问题](#常见问题)

## 实现进度

| Phase | 状态 | 说明 |
|-------|------|------|
| **0 基础设施** | ✅ | FastAPI 工厂、Alembic、Docker Compose (`pgvector/pgvector:pg16`)、structlog |
| **1 账号+对话** | ✅ | JWT + bcrypt、Conversation/Message CRUD、LiteLLM 流式 SSE |
| **2 Agent+MCP** | ✅ | Agent CRUD、ReAct 执行器、工具注册表、MCP HTTP JSON-RPC |
| **3 Workflow** | ✅ | DAG 校验+拓扑执行、节点重试/超时、`{{var}}` 模板渲染 |
| **4 Knowledge/RAG** | ✅ | KB CRUD、文档分块+向量检索+重排、`knowledge_search` 工具 |
| **4.5 四层记忆** | ✅ 文件版 | Working/Core/Episodic/Procedural，`~/.openagentic/memory/` |
| **5 多租户+可观测** | 🟡 | 行级 user_id 隔离 ✓；计费/Prometheus 未实现 |
| **6 前后端闭环** | 🟡 | UI 8 页面完成；Skills/Devices 后端缺失；**CLI 优先，Web 暂缓** |

> **当前优先级：只做 CLI**（对标 Claude Code），Web/App/小程序全部暂缓。

### 已知 Web 端缺口（暂不修）

- `POST /api/knowledge/documents/upload` 前端调用、后端不存在（前端期望默认 KB+文件 multipart，后端要求 `kb_id`+JSON 文本）
- Skills 页面 169 行 UI 就绪，无任何后端 CRUD
- Devices/Sessions/Channels 后端为 Stub 或空
- 记忆系统未暴露到 FastAPI（仅 CLI 可用）

### CLI 当前能力

- **17 个 LLM provider**：OpenAI / Anthropic / DeepSeek / XAI / Gemini / Mistral / Cohere / Groq / OpenRouter / Moonshot / Zhipu / MiniMax / Volcengine / Baidu / Tencent / Nvidia / Together / Fireworks / Qwen / Ollama
- **12 个工具**：`run_command` `read_file` `write_file` `delete_file` `done` + 7 个 memory 工具
- **11 个 slash 命令**：`/model` `/providers` `/automodel` `/clear` `/login-platform` 等
- **写/删文件确认门**：异步确认，REFUSED 由模型重规划
- **REPL 并发输入队列**：输入不阻塞推理
- **四层记忆接入 ReAct loop**：Working 自动压缩 + Core 启动注入 + Episodic 每轮检索
- **DeepSeek V4 Pro/Flash 自动路由**（`/automodel`，支持任意 provider 的二级模型 triage）
- **平台 JWT 登录**（`--api-base` + `/login-platform`）
- **Ctrl+C 中断当轮任务**（不退 CLI，会话保留）
- **底部工具栏**：输入 `/` 实时过滤 slash 命令提示
- **`--no-provider-check`**：跳过 API key 强制配置向导（CI/demo 友好）

### P0 已修复（2026-04）

- `react.py` `tool_call.id` 缺失时自动生成 UUID fallback（兼容 DeepSeek 等不返回 id 的端点）
- `--no-provider-check` + `OPENAGENTIC_SKIP_PROVIDER_CHECK` 跳过 API key 强制配置向导
- `react.py` `repl.py` 4 处 `except Exception: pass` 替换为 `logger.warning(..., exc_info=True)`

### 测试覆盖

137 passed, 2 skipped — 覆盖 CLI 编码、LLM provider 配置、记忆系统、知识库、工作流、MCP、Agent、认证、聊天、迁移脚本、运维烟雾。

## 快速启动

```bash
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic

python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env   # 填写 DATABASE_URL、JWT 密钥、API Key
docker compose up -d postgres

PYTHONPATH=src uvicorn openagentic.main:app --host 0.0.0.0 --port 8000
```

- Swagger：`http://<host>:8000/docs`
- 健康检查：`http://<host>:8000/health`
- 前端：`cd ui && npm install && npm run dev`

**Windows 补充**：拉代码或改依赖后请在仓库根目录再次执行 `pip install -e .`。CLI 不会在进程内自动反复执行 pip install（避免替换正在使用的启动器导致 WinError 32）；源码有更新时请自行重装可编辑包，或直接用 `python -m openagentic.cli`。

## CLI 模式

无需启动 Web 服务，直接在终端对话：

```bash
cd ~/open-agentic && source .venv/bin/activate

# 默认自动选择 provider
python -m openagentic.cli

# 指定 provider 和模型
python -m openagentic.cli --provider deepseek -m deepseek/deepseek-v4-flash

# 带系统提示
python -m openagentic.cli -s "你是一个Python专家，用中文回答"

# 跳过缺 API key 时的强制配置向导（CI/demo）
python -m openagentic.cli --no-provider-check
# 或：OPENAGENTIC_SKIP_PROVIDER_CHECK=1 python -m openagentic.cli

# 注册的命令（需 pip install -e .）
openagentic
```

### 内置命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/config` | 当前 provider/model/endpoint 配置 |
| `/clear` | 清除对话历史（自动存档 episode） |
| `/model` / `/model <name>` | 查看/切换模型 |
| `/providers` / `/provider` / `/provider <id>` | 查看/切换厂商 |
| `/provider-config [id]` | 配置 API Key / API Base |
| `/login-platform` / `/logout-platform` | 平台 JWT 登录/登出 |
| `/automodel [on\|off\|setup]` | 二级模型自动路由 |
| `/quit` | 退出 |

### CLI Memory Tools（7 个）

| Tool | 功能 |
|------|------|
| `core_memory_save` | 保存核心记忆（key/value/category/importance） |
| `core_memory_delete` | 按 key 删除 |
| `core_memory_search` | 关键词搜索核心记忆 |
| `episodic_save` | 保存情节记忆（title/summary/tags） |
| `episodic_search` | 关键词搜索历史片段 |
| `procedural_save` | 保存可复用步骤 |
| `procedural_search` | 搜索匹配的步骤 |

### CLI Provider 说明

- `--provider auto`（默认）：按模型前缀或默认配置自动选择 provider。
- `--provider <id>`：可指定 `openai`、`anthropic`、`xai`、`gemini`、`deepseek`、`qwen`、`ollama` 等 17+ provider。
- CLI 内可用 `/providers` 查看厂商列表，`/provider <id>` 切换并进入配置向导，`/provider-config [id]` 单独编辑配置。
- 未配置 API Key 时，CLI 会在进入会话前强制进入配置向导。如需跳过（CI/demo），加 `--no-provider-check` 或设 `OPENAGENTIC_SKIP_PROVIDER_CHECK=1`。
- Provider 配置文件默认位于 `.openagentic/model_providers.json`（可通过 `MODEL_PROVIDER_CONFIG_PATH` 调整）。

### 二级模型自动路由（`/automodel`）

所有用户输入先由便宜模型做 triage 分类，再决定用哪个模型回答：

```
用户输入 → Simple Model（分类 + 简单回答）
              ├─ SIMPLE → 自己答
              └─ COMPLEX → 升级到 Complex Model → 完成后自动切回
```

- **SIMPLE**：打招呼、事实问答、解释、翻译、摘要、简单文件读取
- **COMPLEX**：写/改代码、调试、架构设计、多步操作、重构、性能优化
- 首次启动若 provider 有 ≥2 个模型且未配置 automodel，自动推断（`flash`/`mini` → simple，`pro`/`max` → complex）并持久化
- `/automodel setup` 交互式手动配置；`/automodel on|off` 开关

### Ctrl+C 中断

REPL 采用 Producer-Consumer 并发模型。模型执行长任务时，**按一次 Ctrl+C 取消当轮 react 任务**（会话保留），再按一次退出 CLI。

### 可用模型参考

**DeepSeek（内置 profile）**：

| 场景 | 模型 |
|------|------|
| 日常对话 / 分类器 | `deepseek/deepseek-v4-flash` |
| 复杂任务 | `deepseek/deepseek-v4-pro` |

**Ollama（本地）**：

| 模型 | 说明 |
|------|------|
| `ollama/qwen3:14b` | Qwen3 14B（带思考） |
| `ollama/qwen3:4b` | Qwen3 4B（轻量） |
| `ollama/deepseek-r1:32b` | DeepSeek R1 32B |

## API 端点

### 认证
- `POST /api/auth/register` / `/login` / `/refresh`
- `GET /api/auth/me`

### 对话
- `GET/POST /api/conversations`
- `GET/DELETE /api/conversations/{id}`
- `GET/POST /api/conversations/{id}/messages`（`stream=true` 时 SSE）

### Agent & 工作流
- `GET/POST /api/agents`、`POST /api/agents/{id}/execute`、`GET /api/agents/{id}/executions`
- `GET/POST /api/workflows`、`POST /api/workflows/{id}/run`

### 知识库
- `GET/POST /api/knowledge`、`POST /{kb_id}/documents`、`POST /{kb_id}/search`、`POST /{kb_id}/optimize-index`

### 其他
- `GET /health`、`GET /api/models`
- `GET/PUT /api/llm/providers`、`PUT /api/llm/default-model`

## 架构

```
ui/ (React + Vite + TailwindCSS + Zustand)
        │ REST + SSE
        ▼
FastAPI ── core/auth · core/chat · core/llm · agent · workflow · knowledge · mcp
        │
        ▼
PostgreSQL 16 + pgvector
```

```
src/openagentic/
├── main.py              # 应用工厂、lifespan
├── config.py / deps.py
├── cli/                 # CLI ReAct（repl、react、tools、providers、model_router 等）
├── core/
│   ├── auth/            # JWT + bcrypt
│   ├── chat/            # 会话+消息+SSE
│   └── llm/             # LiteLLM 网关 + provider 配置
├── agent/               # Agent CRUD + ReAct 执行器 + 工具注册表
├── mcp/                 # MCP HTTP JSON-RPC 客户端
├── workflow/            # DAG 工作流引擎
├── knowledge/           # RAG：知识库 + 向量检索 + 重排序
├── memory/              # 四层记忆系统（文件版）
├── tenant/              # Phase 5 占位
├── observability/       # Phase 5 占位
└── db/                  # session、Base
ui/                      # React 前端
```

**设计原则**：
- **异步优先**：全链路 async（SQLAlchemy async + asyncpg）
- **LiteLLM 统一网关**：17+ provider 收敛为统一接口，换模型 = 改配置
- **模块化单体**：`agent/` `workflow/` `knowledge/` `mcp/` 独立包，按 Phase 填充
- **CLI 平台适配**：`platform_adapter` 统一封装 Windows/Unix 差异

### 技术栈

| 分层 | 选型 |
|------|------|
| 运行时 | Python 3.12 |
| Web 框架 | FastAPI |
| ORM / 驱动 | SQLAlchemy 2.0 async + asyncpg |
| 数据库 | PostgreSQL 16 + pgvector |
| 迁移 | Alembic |
| 配置 | Pydantic Settings |
| LLM 网关 | LiteLLM（17+ provider 统一入口、流式） |
| 认证 | JWT（python-jose）+ bcrypt |
| 前端 | React + Vite + TailwindCSS + Zustand |
| 容器 | Docker Compose |

## 路线图

### Phase 0–4.5（已完成）

基础设施、认证、对话、Agent/MCP、工作流、知识库/RAG、四层记忆系统。

#### 四层记忆系统（Phase 4.5）

存储路径：`~/.openagentic/memory/`

| 层 | 实现 | 接入点 |
|----|------|--------|
| **Working** | 滑动窗口 + LLM 摘要压缩 | `react.py` 每轮按预算压缩 |
| **Core** | 4 类(user_profile/project_fact/preference/reference)，frontmatter+md | 启动时注入 system prompt 前 20 条 |
| **Episodic** | `~/.openagentic/memory/episodes/` | 每轮 ReAct 自动检索 top-3，`/clear` 自动存档 |
| **Procedural** | `~/.openagentic/memory/procedures/` | 模型显式调用 `procedural_save`/`procedural_search`，未自动注入 |

### P1/P2 待办（差距 Claude Code）

- 🔲 长推理无法中断单次任务 → **已修复**（Ctrl+C 取消当轮 react，P1-1）
- 🔲 `write_file` 前无 diff 预览
- 🔲 无 `/plan` 模式
- 🔲 无 `/task` todo list
- 🔲 无子 agent 委派
- 🔲 Procedural memory 不会自动注入

### Phase 5：多租户 + 可观测（未完成）
- [ ] 多租户与组织隔离
- [ ] 用量统计 / 计费 / 配额
- [ ] Prometheus 指标 + correlation ID 全链路追踪

### Phase 6：前后端闭环（部分）
- [x] `ui/` 8 页面框架（Sessions、Settings、Skills、Channels、Devices 等）
- [ ] Skills 后端 CRUD（前端 UI 已就绪）
- [ ] Devices/Sessions/Channels 后端（当前为 stub）
- [ ] 知识库上传 API 前后端对齐
- [ ] 工作流可视化编辑器（React Flow）

### 四层记忆 → DB 版（未来）
- [ ] CoreMemory / Episode / Procedure 迁移到 PostgreSQL + pgvector
- [ ] 语义检索（768-dim，IVFFlat cosine）
- [ ] 时间衰减 + 重要性加权排序
- [ ] `/api/memory/` REST API

## 开发与测试

```bash
# 全量测试（137 passed, 2 skipped）
pytest -q

# CLI 与交互边界
pytest -q tests/cli

# Phase 0 运维烟雾（需 Docker）
pytest -q tests/smoke/test_phase0_ops_smoke.py

# 静态检查
ruff check src tests
mypy
bandit -r src/openagentic -c pyproject.toml
pip-audit
```

### 质量流水线

`.github/workflows/quality-security.yml`：`ruff` + `mypy` + `bandit` + `pip-audit` + `schemathesis`。SonarCloud 见 `.github/workflows/sonarcloud.yml`。

## 常见问题

1. **数据库连不上**：检查 `DATABASE_URL`，确认 Postgres 容器 healthy
2. **表不存在**：生产环境走 `alembic upgrade head`；开发环境 `APP_ENV=development` 可用 `create_all`
3. **SSE 被代理缓冲**：Nginx 需 `proxy_buffering off`
4. **模型 401/429**：核对 API Key；限流时 LiteLLM 自动重试
5. **`ModuleNotFoundError: No module named 'openagentic'`**：未 `pip install -e .`，在仓库根目录执行后重试
6. **`openagentic` 命令找不到**：同上，或直接用 `python -m openagentic.cli`
7. **pip 提示 `Ignoring invalid distribution ~...`**：删除 `.venv/lib/site-packages` 中以 `~` 开头的损坏目录后重装
