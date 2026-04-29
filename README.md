# OpenAgentic

开源 Agent 平台：CLI + HTTP API + Workflow DAG + 知识库 RAG，基于 FastAPI + PostgreSQL/pgvector + LiteLLM。

| 资源 | 链接 |
|------|------|
| 官网 | [openagentic-ai.github.io](https://openagentic-ai.github.io) |
| 仓库 | [github.com/openagentic-ai/open-agentic](https://github.com/openagentic-ai/open-agentic) |
| 许可证 | Apache 2.0 |

## 最近更新

- **2026-04-29**：System-Seed 预设工作流上线（3 个 preset YAML + lifespan upsert + 全渠道透明共享）；并发治理底座 `ConcurrencyGate`（全局信号量 + 类别配额 + 会话串行）；飞书 bot → DAG 工作流链路打通（含用户身份映射 + context 注入）；sender chat_id 自动注入工作流 context；deep logging audit 全覆盖
- **295 passed, 2 skipped** 测试覆盖

## 当前迭代未完成 TODO（2026-04-29，下次接着干）

**目标**：System-Seed 预设工作流收尾 + Workflow resume 引擎 + 5 个生产 bug 收尾。

### 进行中：System-Seed 预设工作流（收尾）

- [x] 1. `Workflow` 模型加 `is_system / slug / version` 字段，`user_id` 改 nullable
- [x] 2. Alembic 迁移 `add_is_system_workflow`
- [x] 3. 3 个预设 YAML：`presets/doc.summarize_url.yaml` / `news.tech_weekly.yaml` / `ops.server_health.yaml`
- [x] 4. Preset loader：`src/openagentic/workflow/presets.py`（`_scan_presets` + `load_presets`）
- [x] 5. `tool` 节点扩展支持 `args: dict` 入参
- [x] 6. `main.py` lifespan 调用 `_load_preset_workflows()`
- [x] 7. `service.list_workflows` 合并 `user_id == current OR is_system==True`
- [x] 8. `channel_runner.py` WORKFLOW_TOOLS 预设提示（slug → run_workflow 直调）
- [x] 9. sender_open_id / chat_id 注入工作流 context（`contextvars` → `input_data.context`）
- [x] 10. 并发治理底座 `ConcurrencyGate`（全局信号量 + 类别配额 + 会话串行）
- [x] 11. `service.update_workflow` / `delete_workflow` 拒绝 `is_system=True`（抛 `SystemWorkflowImmutable` → 路由 403）+ `POST /api/workflows/{id}/fork` 端点
- [x] 12. `start_workflow_run` / `get_workflow` 已合并 `or is_system`；系统 run 归属调用者（`calling_user_id`）
- [x] 13. 写测试：`tests/workflow/test_presets.py` — 14 条覆盖 YAML 解析/扫描/upsert/版本策略/真实预设健全度/不可改不可删/fork
- [ ] 14. **遗留小修（非阻塞）**：`add_is_system_workflow.py` 同时建 `uq_workflows_slug` UNIQUE 约束 + `ix_workflows_slug` 普通索引——同一列两个索引冗余；建议下个迁移里 drop 后者，并把模型 `slug` 字段去掉 `index=True`

### 待修：生产 bug

- [ ] **#1 15 服部署**：`/opt/open-agentic` 更新代码 + `alembic upgrade head` + `systemctl restart`
- [ ] **#2 LLM 不用 list_workflows**：preset 提示已注入 system prompt，需验证实际效果
- [ ] **#3 DAG 被绕过**：同 #2，preset hints 兜底
- [ ] **#4 sender_open_id 注入**：contextvars 链路已就绪，pr
- [ ] **#5 飞书 markdown 渲染**：`feishu_card_utils.py` + `feishu.py:_send_via_cli`，下次单 PR

### 上线动作（合并完上述 11-14 + bug 修复后一次性做）

```bash
# 本机
pytest -q
git add -A && git commit -m "feat: system-seed preset workflows 收尾"
git push origin main

# 15 服务器
ssh root@192.168.0.15
cd /opt/open-agentic
git pull origin main --ff-only
.venv/bin/alembic upgrade head
systemctl restart openagentic-feishu.service
journalctl -u openagentic-feishu.service -f
```



## 目录

- [实现进度](#实现进度)
- [快速启动](#快速启动)
- [CLI 模式](#cli-模式)
- [API 端点](#api-端点)
- [架构](#架构)
  - [请求生命周期](#请求生命周期)
  - [CLI ReAct 循环](#cli-react-循环)
  - [四层记忆系统](#四层记忆系统)
  - [Skills 系统](#skills-系统)
  - [数据库概要](#数据库概要)
  - [Workflow DAG 引擎](#workflow-dag-引擎)
  - [设计决策](#设计决策)
- [路线图](#路线图)
- [开发与测试](#开发与测试)
- [常见问题](#常见问题)
- [隐私政策](#隐私政策)
- [贡献指南](#贡献指南)

## 实现进度

| Phase | 状态 | 说明 |
|-------|------|------|
| **0 基础设施** | ✅ | FastAPI 工厂、Alembic、Docker Compose (`pgvector/pgvector:pg16`)、structlog |
| **1 账号+对话** | ✅ | JWT + bcrypt、Conversation/Message CRUD、LiteLLM 流式 SSE |
| **2 Agent+MCP** | ✅ | Agent CRUD、ReAct 执行器、工具注册表、MCP HTTP JSON-RPC |
| **3 Workflow** | ✅ | DAG 校验（结构/唯一 id/支持类型/无环）+ 拓扑序执行；节点级 `retries` / `timeout_sec`；`{{input.x}}` `{{nodes.<id>}}` 模板渲染；软取消 + 协程 cancel 双通道；结构化 trace（每节点 status/attempt/output/error） |
| **4 Knowledge/RAG** | ✅ | KB CRUD、文档分块+向量检索+重排、`knowledge_search` 工具 |
| **4.5 四层记忆** | ✅ 文件版 | Working/Core/Episodic/Procedural，`~/.openagentic/memory/` |
| **5 多租户+可观测** | ✅ 单租户级 | 行级 user_id 隔离 ✓；tenant/request_id contextvar ✓；Prometheus `/metrics` ✓；structlog 注入 request_id+tenant_id ✓ |
| **5.5 CLI 增强** | ✅ | `/compact` `/context` `/btw` `/cost` `/permissions` `/diff` `/review` + procedural 自动注入 + `write_file` diff + 6 个内置 SKILL |
| **6 前后端闭环** | ✅ | 知识库上传 API 对齐；Skills/Channels/Sessions/Devices 全 CRUD 上线；前端全部接入真实 API；Android 客户端可用 |
| **7 Workflow 扩展** | 🔄 进行中 | System-Seed 预设工作流（3 preset + lifespan upsert）；并发底座 `ConcurrencyGate`；sender context 注入；飞书 bot → DAG 链路；suspended 状态机 + runtime 挂起；`feishu`/`wecom`/`approval`/`human_input` 4 新节点类型 |

### CLI 当前能力

- **20 个 LLM provider**：OpenAI / Anthropic / DeepSeek / XAI / Gemini / Mistral / Cohere / Groq / OpenRouter / Moonshot / Zhipu / MiniMax / Volcengine / Baidu / Tencent / Nvidia / Together / Fireworks / Qwen / Ollama
- **12 个工具**：`run_command` `read_file` `write_file` `delete_file` `done` + 7 个 memory 工具
- **19 个 slash 命令**：`/model` `/providers` `/automodel` `/clear` `/login-platform` `/skills` `/compact` `/context` `/btw` `/cost` `/permissions` `/diff` `/review` 等
- **Skills 系统**（Claude Code 风格）：`~/.openagentic/skills/<slug>/SKILL.md`，frontmatter+markdown，启动时 metadata 注入 system prompt（每条 ~50 token），全文按需 `read_file` 加载。内置 6 个：`git-commit` / `code-review` / `debug-trace` / `security-review` / `simplify` / `batch`。`/skills` 列表，`/skills <name>` 看详情，`/skills new <name>` 建模板，`/skills reload` 热加载
- **写/删文件确认门**：异步确认，REFUSED 由模型重规划；**root 命令**（`sudo` / `doas` / `pkexec` / `su`）即使 policy=allow 也强制 Y/N 确认
- **`/permissions` 策略**：4 个 gated tool（read/run/write/delete）按 `allow / ask / deny` 三档管控，支持文件路径白/黑名单与 `run_command` 前缀白/黑名单，存于 `~/.openagentic/permissions.json`
- **`/cost` 会话成本**：per-model token + USD 估算（litellm.completion_cost），`/clear` 自动重置
- **`write_file` diff 预览**：覆盖时在 confirm 提示中展示 unified diff（>80 行截断，二进制降级为字节数预览）
- **REPL 并发输入队列**：输入不阻塞推理
- **四层记忆接入 ReAct loop**：Working 自动压缩 + Core 启动注入 + Episodic 每轮检索 + Procedural 每轮 top-3 注入
- **DeepSeek V4 Pro/Flash 自动路由**（`/automodel`，支持任意 provider 的二级模型 triage）
- **平台 JWT 登录**（`--api-base` + `/login-platform`）
- **Ctrl+C 中断当轮任务**（不退 CLI，会话保留）
- **底部工具栏**：输入 `/` 实时过滤 slash 命令提示
- **`--no-provider-check`**：跳过 API key 强制配置向导（CI/demo 友好）

### P0 已修复（2026-04）

- `react.py` `tool_call.id` 缺失时自动生成 UUID fallback（兼容 DeepSeek 等不返回 id 的端点）
- `--no-provider-check` + `OPENAGENTIC_SKIP_PROVIDER_CHECK` 跳过 API key 强制配置向导
- `react.py` `repl.py` 4 处 `except Exception: pass` 替换为 `logger.warning(..., exc_info=True)`
- `/cost`（per-model token+USD）、`write_file` 覆盖时 unified diff 预览、`/permissions`（allow/ask/deny + 路径/前缀白/黑名单）全部落地
- **root 命令强制确认**：`sudo` / `doas` / `pkexec` / `su` token 级匹配（避免 `sudoku` 误伤），即使 policy=allow 或命中 allow_prefixes 也强制 Y/N
- **代码瘦身**：`repl.py` 949 → 434 行，提取 `cli/slash_commands.py`（567 行）承接所有 `_handle_*` 处理器与 UI 原语；`main_loop` 535 → 408 行，`_execution_consumer` 325 → 198 行，全项目 .py 文件均 ≤ 800 行

### 测试覆盖

295 passed, 2 skipped — 覆盖 CLI 编码、`/cost` / `write_file` diff / `/permissions`、root 命令强制确认、LLM provider 配置、记忆系统、知识库、工作流（含 presets + suspended）、MCP、Agent、认证、聊天、迁移脚本（7 个 revision）、运维烟雾、数据库会话、可观测性、Skills 系统、租户上下文、并发网关。

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
| `/compact` | 立即压缩 working memory（同自动阈值触发） |
| `/context` | 显示当前消息条数、role 分布、估算 token、压缩阈值 |
| `/btw <text>` | 把一句备注追加进对话上下文，**不触发推理**（高频补充用） |
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
- `GET/POST /api/workflows`、`GET/PATCH/DELETE /api/workflows/{id}`
- `POST /api/workflows/{id}/runs`（创建并立即执行一次 run）
- `GET /api/workflow-runs?workflow_id=…`、`GET /api/workflow-runs/{run_id}`
- `POST /api/workflow-runs/{run_id}/cancel`（软取消：写入标志 + 协程 cancel）

### 知识库
- `GET/POST /api/knowledge`、`POST /{kb_id}/documents`、`POST /{kb_id}/search`、`POST /{kb_id}/optimize-index`
- `POST /api/knowledge/documents/upload`（multipart 文件上传）、`GET /api/knowledge/documents`、`DELETE /api/knowledge/documents/{id}`
- `POST /api/knowledge/search`（跨知识库检索）

### 记忆系统
- `GET /api/memory/core`、`GET /api/memory/core/search?q=`、`POST /api/memory/core`、`DELETE /api/memory/core/{key}`
- `GET /api/memory/episodes/search?q=`、`POST /api/memory/episodes`
- `GET /api/memory/procedures/search?q=`、`POST /api/memory/procedures`

### Skills
- `GET /api/skills`、`GET /api/skills/{slug}`、`POST /api/skills`

### Sessions & Channels & Devices
- `GET/POST /api/sessions`、`DELETE /api/sessions/{id}`
- `GET/POST /api/channels`、`DELETE /api/channels/{id}`
- `GET /api/devices`

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
├── identity.py          # 全局 Agent 身份与行为准则（CLI/飞书/企微共享）
├── cli/                 # CLI ReAct（repl、react、tools、providers、model_router 等）
├── channels/            # 渠道配置 DB 模型 + 管理 CRUD
├── concurrency/         # 并发治理网关（全局信号量 + 类别配额 + 会话串行）
├── core/
│   ├── auth/            # JWT + bcrypt
│   ├── chat/            # 会话+消息+SSE + sessions 兼容路由
│   └── llm/             # LiteLLM 网关 + provider 配置
├── devices/             # 设备节点与能力目录
├── agent/               # Agent CRUD + ReAct + 工具注册表
│   ├── engine.py        # ConversationEngine——LLM+工具循环共享底座
│   └── llm.py           # litellm_chat 抽象（DeepSeek thinking 兼容）
├── mcp/                 # MCP HTTP JSON-RPC 客户端
├── workflow/            # DAG 工作流引擎
├── knowledge/           # RAG：知识库 + 向量检索 + 重排序
├── memory/              # 四层记忆系统（文件版 + REST API）
├── skills/              # CLI skills（Claude Code 风格 SKILL.md，含 builtin/ + REST API）
├── tenant/              # 请求级 tenant_id / request_id contextvar
├── observability/       # structlog 配置 + Prometheus + RequestContextMiddleware
└── db/                  # session、Base
ui/                      # Web 前端（React + Vite + Tailwind + Zustand）
extensions/              # 扩展模块（与 core 完全解耦）
├── channels/            # 飞书 + 企业微信渠道集成
│   ├── base.py          # Channel 抽象接口 + 生命周期
│   ├── feishu.py        # 飞书渠道（SDK WebSocket + 卡片 + CLI）
│   ├── wecom.py         # 企业微信渠道（XML 解密 + CLI）
│   └── router.py        # 动态路由工厂
└── android/             # Android 客户端（聊天/Settings/多语言/SSE，完整可用）
scripts/
└── run_feishu_ws.py     # 飞书独立运行脚本（不依赖 PostgreSQL）
tests/
├── test_*.py            # 根级：Agent、workflow、knowledge、MCP、认证、聊天、记忆、迁移等
├── cli/                 # CLI 编码、slash 命令、交互边界
├── db/                  # 数据库会话测试
├── observability/       # 日志、指标、中间件测试
├── skills/              # Skill 加载器与管理器测试
├── tenant/              # 租户 contextvar 测试
├── config/              # 配置加载与校验
├── deps/                # FastAPI 依赖注入
├── entry/               # CLI 入口参数解析
└── smoke/               # Phase 0 运维烟雾（需 Docker）
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

### 请求生命周期

```
Incoming Request
  → CORS (CORSMiddleware)
    → RequestContextMiddleware
        • 提取/生成 X-Request-ID（UUID hex），写入 contextvar，回带响应头
        • 解码 Authorization JWT 提取 sub → tenant_id contextvar
      → Prometheus Instrumentator（method/path_template/status 三维标签）
        → FastAPI route
          → get_current_user（HTTPBearer → jose.jwt → DB lookup → 401）
            → Service 层（所有查询强制过滤 user_id）
              → DB session（asyncpg pool=20+10）
                → Response
```

- **contextvar 传递**：`tenant_id` 和 `request_id` 在整个调用栈中通过 contextvar 传播，structlog 每行日志自动注入
- **不强制认证**：中间件仅解码 JWT 不拦截——认证在路由级 `Depends(get_current_user)` 执行
- **Prometheus 排除**：`/health` `/metrics` 自身不统计，label 不含 `tenant_id`（控制基数）

### CLI ReAct 循环

CLI 采用 **Producer-Consumer 并发模型**：

```
prompt_toolkit (生产者)              asyncio consumer (消费者)
       │                                      │
       ├─ 用户输入 → asyncio.Queue ──────────→├─ 取消息
       │                                      ├─ slash 命令？→ 直接处理，不调 LLM
       │                                      ├─ 用户消息：
       │                                      │   1. automodel triage（SIMPLE/COMPLEX）
       │                                      │   2. episodic_search(用户输入, top-3) → 注入 messages[1]
       │                                      │   3. procedural_search(用户输入, top-3) → 注入 messages[1]
       │                                      │   4. working_memory_compressible? → compress()
       │                                      │   5. litellm_chat(messages + TOOLS) ← 带 spinner 动画
       │                                      │   6. 返回 content → render markdown → done
       │                                      │   7. 返回 tool_calls → 逐个执行 → 回填 tool result → goto 5
       │                                      │   8. done tool → render → return
       │                                      └─ 最多 1000 轮迭代
       └─ Ctrl+C → 取消当前 react task（不退 CLI）
```

**关键路径**：

- **权限门控**（`read_file` / `run_command` / `write_file` / `delete_file`）：
  ```
  policy=deny → REFUSED
  hit deny_paths/deny_prefixes → REFUSED
  hit allow_paths/allow_prefixes → ALLOWED（跳过确认）
  policy=allow → ALLOWED（跳过确认）
  policy=ask → 弹出 Y/N 确认
  ```
  特例：`sudo` / `doas` / `pkexec` / `su` token 级匹配，无论策略一律强制 Y/N

- **`write_file` diff 预览**：覆盖时在 confirm 提示中展示 unified diff（>80 行截断，二进制降级为字节数预览）

- **压缩触发**：`chars/3` 估算 token 数（CJK 保守），超 6000 token 阈值自动压缩；保留 system prompt + 最近 8 条消息，旧消息 LLM 摘要为 3-6 点，以 `[Conversation Summary]` system message 插入

### 四层记忆系统

存储根：`~/.openagentic/memory/`

```
~/.openagentic/memory/
├── MEMORY.md                    # 自动重建的索引入口（每次写入后更新）
├── core/
│   ├── user_profile/            # 用户画像（*.md，frontmatter + body）
│   ├── project_fact/            # 项目事实
│   ├── preference/              # 偏好设置
│   └── reference/               # 参考信息
├── episodes/                    # 对话摘要（YYYY-MM-DD-slug-uuid.md）
└── procedures/                  # 可复用步骤（safe_name.md）
```

**注入时机与机制**：

| 层 | 注入时机 | 机制 |
|----|---------|------|
| **Working** | 每轮 LLM 调用前 | `chars/3` 估算 token → 超 6000 阈值触发 `compress_working_memory()`，旧消息 LLM 摘要为 3-6 点，累积合并已有 `[Conversation Summary]` |
| **Core** | 启动时 | `list_core(limit=20)` 按 importance desc 排序，注入 system prompt 顶部 `## Persistent Core Memory` 区块 |
| **Episodic** | 每轮用户输入后 | `search_episodes(user_input, top_k=3)` 关键词匹配，注入 `messages[1]`（紧跟 system prompt） |
| **Procedural** | 每轮用户输入后 | `search_procedures(user_input, top_k=3)` 关键词匹配（词干匹配 3x 加权），注入 `messages[1]` |

**MEMORY.md 索引**：每次 `save_core_memory` / `delete_core_memory` / `save_episode` / `save_procedure` 后自动重建全量索引。这是人类可读的入口，也是 Claude Code 兼容的记忆格式。

**当前局限**：文件版，无向量检索。未来计划迁移 PostgreSQL + pgvector 做语义检索。

### Skills 系统

Skills 是 **文件式 SOP 模板**——不是工具，是给模型看的领域操作指南。

**存储格式**：`~/.openagentic/skills/<slug>/SKILL.md`

```markdown
---
name: git-commit           # 必填，须等于目录名（kebab-case）
description: 提交代码时用  # 必填，含触发条件
allowed-tools: [...]       # 可选，限定可用工具列表
---

# git-commit

## 何时使用
...

## 操作步骤
...
```

**注入策略**：
- **启动时**：`build_skills_section()` 扫描 `~/.openagentic/skills/`，仅注入元数据（name + description + 路径，~50 token/skill）
- **运行时**：模型判定任务匹配某 skill → 调用 `read_file` 加载完整 SKILL.md → 按指南执行
- **热加载**：`/skills reload` 重新扫描并重建 system prompt，无需重启

**生命周期**：
- 首次启动：`ensure_seeded()` 从 `src/openagentic/skills/builtin/` 复制 3 个内置 skill 到 `~/.openagentic/skills/`（`.seeded` 标记防止重复）
- 用户自定义：`/skills new <name>` 创建模板 → 手动编辑 SKILL.md → `/skills reload`
- **不覆盖原则**：如果用户目录已存在同名 slug，内置 skill 不覆盖

内置 3 个：`git-commit`（生成 conventional commit）、`code-review`（系统化代码审查，含 severity 分级）、`debug-trace`（结构化调试：复现 → trace → 定位 → 假设 → 修复）。

### 数据库概要

6 大域，所有业务表带 `user_id` FK 实现行级多租户：

```
users ─┬─ api_keys              # JWT 认证
       ├─ conversations ─┬─ messages     # 对话（含 reasoning_content 列）
       ├─ agents ────────── agent_executions   # Agent 执行记录（JSON steps + trace）
       ├─ workflows ─────── workflow_executions # Workflow 执行（含 is_system/slug/version 预设字段）
       ├─ knowledge_bases ─┬─ documents ─┬─ chunks   # RAG（pgvector Vector(768)）
       ├─ channel_configs        # 渠道配置（飞书/企微 app 凭证）
       └─ user_channel_bindings  # 外部渠道账号 → User 映射
```

| 域 | 核心表 | 关键字段 |
|----|-------|---------|
| 认证 | `users` `api_keys` | UUID PK, `email`(unique), `hashed_password`, bcrypt |
| 对话 | `conversations` `messages` | `role` enum(user/system/assistant/tool), `reasoning_content`, `token_count_input/output`, `cost_usd` |
| Agent | `agents` `agent_executions` | `tools` JSON, `config` JSON, `steps` JSON, `status` enum |
| Workflow | `workflows` `workflow_executions` | `definition` JSONB, `input_data`/`output_data` JSON, `node_states` JSON(trace+cancel), `status` enum(pending/running/completed/failed/cancelled) |
| 知识库 | `knowledge_bases` `documents` `chunks` | `embedding` Vector(768), `chunk_size`/`chunk_overlap`, `metadata_` JSON |
| 迁移 | 7 个 Alembic revisions | 初始→workflow→knowledge(pgvector)→reasoning_content→suspended status→user_channel_bindings→is_system_workflow |

- **多租户**：应用层 `user_id` 过滤，非 RLS；`tenant_id` contextvar 等价 `user_id`
- **WorkflowExecution 特殊**：`node_states` 一个 JSONB 同时承载 trace 数组和 `_cancel_requested` 软标志
- **Chunk 无 TimestampMixin**：仅 `created_at`，无 `updated_at`

### 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 架构风格 | 模块化单体 | Phase 0-5 单进程部署足够，`agent/` `workflow/` `knowledge/` `mcp/` 独立包边界清晰；未来可按包拆微服务 |
| LLM 网关 | LiteLLM | 17+ provider 统一为 `model` 字符串 + 配置，换模型只改配置不写代码；社区维护成本低 |
| 异步栈 | SQLAlchemy async + asyncpg | 全链路 async 避免 IO 阻塞事件循环，asyncpg 原生 PostgreSQL 二进制协议性能优于 psycopg2 |
| 记忆存储 | 文件版（frontmatter+md）先于 DB+pgvector | 零依赖启动、人类可读可编辑、与 Claude Code MEMORY.md 格式兼容；向量检索版留待 Phase 未来 |
| 模板渲染 | 字符串替换而非 Jinja | Workflow DAG 场景 `{{input.x}}` `{{nodes.id}}` 够用，复杂逻辑走 `tool` 节点封装，避免引擎膨胀 |
| DAG 执行 | 串行先于并行 | 先保证正确性和结构化 trace；同层 `asyncio.gather` 留 Phase 7 |
| 取消机制 | 双通道（软标志 + 协程 cancel） | 软标志覆盖"节点边界优雅停"，`asyncio.Task.cancel()` 覆盖"长跑节点立即停" |
| Skills | SKILL.md 文件式而非硬编码 slash | 行为类功能（review/commit/debug）统一为可编辑 SOP 文档，模型按需 read_file 加载全文，避免命令膨胀 |
| MCP | HTTP JSON-RPC 客户端（非 stdio） | 先支持远程 MCP server，stdio 本地 server 后续按需补 |
| 重排序 | CrossEncoder（`rerank_model`） | 向量检索后对 top-N 做精排，提升 RAG 准确率；轻量级模型不依赖外部服务 |
| 系统预设 | `presets/*.yaml` + lifespan upsert | 启动自动同步预设工作流到 DB，跨渠道透明共享；按 slug+version 升降级判断，用户不可改只能 fork |
| 并发治理 | `ConcurrencyGate`（全局信号量 + 类别配额 + 会话串行） | 多用户并发请求统一接入，飞书/企微/CLI/HTTP 共享同一套限流 + 排队 + 超时兜底 |

### Workflow DAG 引擎

轻量 DAG 引擎；节点连接器 / 审批 / 可视化 / 版本回滚等扩展见 [Phase 7](#phase-7workflow-扩展)。

#### 定义格式（`workflows.definition`）

```json
{
  "nodes": [
    {"id": "input",  "type": "value", "config": {"value": "{{input.question}}"}},
    {"id": "answer", "type": "llm",   "config": {
        "system_prompt": "你是 SOP 助手",
        "prompt": "请回答：{{nodes.input}}",
        "model": "deepseek/deepseek-v4-flash",
        "retries": 1,
        "timeout_sec": 30
    }}
  ],
  "edges": [{"from": "input", "to": "answer"}]
}
```

#### 节点类型（8 种）

| type   | 行为 | 关键 config |
|--------|------|-------------|
| `value` | 把字面量/渲染后字符串作为输出 | `value` |
| `tool`  | 调用工具注册表中的工具 | `tool_name`、`arg`（透传给工具的 input/query/command） |
| `llm`   | 走 LiteLLM 网关 chat completion | `prompt`（必填）、`system_prompt`、`model` |
| `feishu` | 执行 `lark-cli` CLI 命令 | `subcommand`（必填）、`args`（数组） |
| `wecom` | 执行 `wecom-cli` CLI 命令 | `subcommand`（必填）、`args`（数组） |
| `approval` | 触发审批 → run 进 suspended → 等回调 | `channel`、`approval_code` |
| `human_input` | 发卡片 → run 进 suspended → 等提交 | `channel`、`prompt`、`instance_key` |
| `subflow` | 调用另一个 workflow（计划中） | — |

#### 校验（`validate_definition`）

创建 / 更新工作流时强制：

- `nodes` 非空数组、`edges` 数组
- 节点 `id` 非空且全局唯一
- 节点 `type` ∈ {`value`, `tool`, `llm`, `feishu`, `wecom`, `approval`, `human_input`}
- `edges` 两端必须指向已存在节点
- **拓扑排序必须能完整覆盖所有节点**——否则判定有环并 `400 Bad Request`

#### 执行模型

1. `POST /api/workflows/{id}/runs` 创建一条 `WorkflowExecution`（status=`pending`）并立即执行
2. 状态机：`pending → running → (suspended → running)* → completed | failed | cancelled`
3. 拓扑序**串行执行**节点；当前未做并行调度（同层节点不并发）
4. 每个节点执行前先 `db.refresh(run)` 检查取消标志，命中即 break
5. 节点 config 渲染 `{{input.…}}` / `{{nodes.<id>}}` 模板（递归遍历 dict/list/str）
6. 节点级容错：`asyncio.wait_for(timeout_sec)` 包裹 + `retries` 次重试（默认 timeout=60、retries=0）
7. 任意节点超过重试预算未成功 → 整个 run `failed` 并写入 `node_states.error`
8. 整图最后一个拓扑节点的输出作为 run 的 `output_data.result`

#### 模板变量

```
{{input.<key>}}        # POST run 时传入的 input_data
{{nodes.<node_id>}}    # 已执行节点的输出（按拓扑序）
```

不支持表达式 / 过滤器 / 条件——是字符串替换不是 Jinja，刻意收窄能力以避免引擎复杂化。需要分支逻辑请走 `tool` 节点封装。

#### 取消（双通道）

`POST /api/workflow-runs/{run_id}/cancel` 同时做两件事：

- **软标志**：写 `node_states._cancel_requested = True`，下一节点循环开头被感知后写入 `cancelled` trace 并 break
- **硬中断**：`runtime.cancel(run_id)` 触发 `asyncio.Task.cancel()`，正在 `wait_for` 内的节点立即抛 `CancelledError`，被 `execute_run` 统一映射为 `cancelled`

软标志解决"节点边界优雅停"，硬中断解决"长跑节点立即停"。

#### 执行 Trace（`node_states.trace`）

每个节点至少产出一条 trace 项：

```json
{"node_id": "answer", "node_type": "llm", "status": "success",  "attempt": 1, "output": "…"}
{"node_id": "answer", "node_type": "llm", "status": "retrying", "attempt": 1, "error": "…"}
{"node_id": "answer", "node_type": "llm", "status": "failed",   "attempt": 2, "error": "…"}
{"node_id": "answer",                       "status": "cancelled", "reason": "cancel_requested"}
```

通过 `GET /api/workflow-runs/{run_id}` 整体回看，目前**没有 SSE/流式 trace 推送**——见 Phase 7 待办。

#### 系统预设工作流

3 个开箱即用的预设，启动时自动 upsert 到 DB（`user_id=NULL, is_system=True`），跨渠道（CLI/飞书/企微/HTTP）透明共享：

| slug | 名称 | 用途 |
|------|------|------|
| `news.tech_weekly` | 技术新闻周报 | 抓取科技媒体 RSS/API → LLM 摘要分类 → 生成中文周报 |
| `doc.summarize_url` | URL 摘要 | 抓取指定网页 → LLM 提炼要点 → 结构化摘要输出 |
| `ops.server_health` | 服务器健康巡检 | SSH/HTTP 检查目标主机 → 汇总磁盘/内存/服务状态 → 告警 |

**机制**：`main.py` lifespan 调用 `load_presets(db)` 按 `slug` 匹配已有记录，`version` 字段控制升级；同 slug 新版覆盖、旧版跳过、不变跳过。channel_runner 注入预设提示到 system prompt，LLM 识别到"新闻周报"等意图时直接 `run_workflow(slug)`。

用户不能修改/删除系统预设——需 fork 成私有副本后再编辑。

#### 当前不支持

- 同层并行执行 / 调度器（DAG 引擎刻意串行）
- 子工作流 / 工作流互调（`subflow` 节点计划中）
- `approval` / `human_input` 节点的真正飞书审批/卡片回调集成（骨架已就绪，事件触发器待接）
- WorkflowTrigger 表 + 事件驱动启动 workflow
- 版本管理 / 灰度 / 回滚
- Workflow resume 接口（`POST /api/workflow-runs/{id}/resume`）

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

### Phase 5：多租户 + 可观测

- [x] 行级 `user_id` 隔离（已存在于 db schema）
- [x] 请求级 tenant context（`tenant/` contextvar，`tenant_id == user_id`）
- [x] Prometheus `/metrics`（method/path_template/status 三维标签，`/health` `/metrics` 自身排除）
- [x] structlog 自动注入 `request_id` 与 `tenant_id`，`X-Request-ID` 中间件透传/生成
- [ ] 组织(Org)级隔离（需新表 `organizations`、`user_organizations`，全路由 scope 改造）
- [x] 跨服务 correlation（LiteLLM 注入 `x-request-id` / `x-tenant-id`；DB 通过 structlog 关联）

### Phase 5.5：CLI 增强

#### 已完成

- [x] `/skills` 命令 + Skills 系统（Claude Code 风格 SKILL.md，3 个内置）
- [x] Ctrl+C 中断单轮 react（保留会话）
- [x] `--no-provider-check` 跳过 API key 强制配置向导
- [x] `/compact` `/context` `/btw` 三命令
- [x] Procedural memory 自动注入
- [x] `/cost`（per-model token + USD 估算）
- [x] `write_file` 覆盖时 unified diff 预览
- [x] `/permissions`（allow/ask/deny + 路径/前缀白/黑名单）

#### 待办

| 任务 | 优先级 | 备注 |
|---|---|---|---|
| ~~`/diff`（包 `git diff` + rich 染色）~~ | ~~P1~~ | ✅ 已落地 |
| ~~`/review`（喂 git diff + code-review skill）~~ | ~~P1~~ | ✅ 已落地 |
| ~~3 个内置 SKILL：`security-review` / `simplify` / `batch`~~ | ~~P1~~ | ✅ 已落地（内置 skill 增至 6 个） |
| 全套烟测（所有新命令 + 3 SKILL 通过 LLM 触发验证） | P2 | 单元测试已补齐，LLM 端到端待后续 |

#### 不做

- `/copy`（终端自带复制）
- `/plan`（做成 `planner` SKILL 更优雅）
- 跨端联动 `/desktop` `/mobile` `/chrome`、商业化 `/upgrade` `/passes`、第三方集成 `/install-github-app`、基础设施大工程 `/sandbox` `/heapdump`、依赖未建系统 `/loop` `/rewind`、多模态 `/voice`
- 行为类（`/batch` `/simplify` `/security-review` `/debug` 等）→ 统一走 SKILL.md 路线，不做硬编码 slash

### Phase 5.6：企业微信 + 飞书 渠道集成（已上线）

让 OpenAgentic 以飞书/企业微信为交互界面——用户发消息 → agent 处理 → 回复消息。同时支持 agent 调用飞书/企微 CLI 操作文档、日历、多维表格等。

#### 架构设计

```
extensions/channels/          # 渠道层（与 core 完全解耦）
├── __init__.py               # 注册中心，环境变量自动发现
├── base.py                   # Channel 抽象接口 + IncomingMessage
├── feishu.py                 # 飞书渠道：SDK WebSocket + 卡片 + CLI
├── wecom.py                  # 企业微信渠道：XML 解密 + CLI
└── router.py                 # 动态路由工厂（GET/POST webhook）

scripts/
└── run_feishu_ws.py          # 独立运行脚本，不依赖 PostgreSQL

src/openagentic/
├── agent/
│   ├── engine.py             # NEW ConversationEngine（共享底座）
│   ├── llm.py                # NEW litellm_chat 抽象（从 cli/llm 提取）
│   └── ...
└── identity.py               # NEW 全局 Agent 身份与行为准则
```

**关键设计决策**：

| 决策 | 选择 | 理由 |
|------|------|------|
| 收消息 | WebSocket 长连接（飞书 SDK） | 无需公网 URL；`lark-oapi` 内部处理 token/重连 |
| 发消息 | SDK 直发（优先）/ CLI（备选） | SDK 毫秒级，CLI 有子进程开销 |
| 不走 MCP | 拒绝 | 常驻进程运维负担 > 收益；WebSocket + SDK 已覆盖 |
| 渠道隔离 | `extensions/channels/` | 环境变量激活，未配置零开销 |
| LLM 调用 | `ConversationEngine`（`agent/engine.py`） | CLI / 飞书 / 企微 / HTTP API 共享同一底座 |
| 回复形式 | 交互卡片（"思考中..." → 原地替换） | SDK 直发卡片，`update_card` 实现渐进式反馈 |

#### 已完成

| # | 任务 | 说明 |
|---|------|------|
| 1 | Channel 抽象基类 | `extensions/channels/base.py` — 生命周期 `start()`/`stop()` |
| 2 | 飞书渠道 | WebSocket 长连接 + 交互卡片 + SDK 直发 + CLI 备选 |
| 3 | 企业微信渠道 | XML 验签/解密 + `wecom-cli` 发送 |
| 4 | FastAPI 渠道路由 | webhook 端点 + 生命周期集成 |
| 5 | ConversationEngine | 共享底座：LLM 调用 + 工具循环，各渠道复用 |
| 6 | Agent 身份准则 | `identity.py` — `build_system_prompt()` 统一入口 |
| 7 | 飞书独立运行脚本 | `scripts/run_feishu_ws.py` — 不依赖 PostgreSQL |
| 8 | 端到端验证 | 飞书消息 → 卡片思考 → AI 回复 → 原地替换 ✅ |
| 9 | 工具集成 | `run_command` + `read_file` + `lark-cli`（22 模块：日程/文档/多维表格/审批/消息/通讯录/云盘/邮箱/任务/知识库/表格/幻灯片/会议纪要/视频会议/白板/考勤/OKR/通用 API 等） |
| 10 | DeepSeek thinking 兼容 | `reasoning_content` 空 content 引擎兜底处理 |
| 11 | 飞书权限全开 | 131 个权限 scope，企业自建应用最大权限集 |
| 12 | Agent 身份准则 | `identity.py` — 完整能力清单 + 隐私铁律（禁止泄露搭建者信息） |
| 13 | 全项目隐私排查 | 测试数据去个人化、源代码零硬编码密钥、`.env` gitignored |

#### TODO

| # | 任务 | 优先级 | 备注 |
|---|------|--------|------|
| 1 | 企业微信端到端验证 | P1 | 需企微开发者账号 |
| 2 | ~~企微独立运行脚本~~ | ~~P2~~ | ✅ 已落地（`scripts/run_wecom_ws.py`，复用 `ChannelAIService`） |
| 3 | ~~Markdown 表格自动转卡片 component~~ | ~~P2~~ | ✅ 已落地（`feishu_card_utils.py`，含卡片 JSON 构建抽象） |
| 4 | 飞书流式卡片（打字机效果） | P3 | 参考 `hermes-feishu-streaming-card` |
| 5 | 钉钉渠道集成 | P3 | 待钉钉 CLI 成熟 |

#### 当前不做

- MCP 协议通道
- 多租户飞书/企微 app 绑定

### Phase 6：前后端闭环（已完成）

- [x] `ui/` 8 页面框架（Sessions、Settings、Skills、Channels、Devices 等）
- [x] CLI Skills 系统（文件式 Claude Code 风格）
- [x] Skills REST API（`GET/POST /api/skills`），前端 SkillsPage 接入真实数据
- [x] Sessions CRUD（映射 Conversation 模型），前端 SessionsPage 对接
- [x] Channels 管理 CRUD（`ChannelConfig` DB 模型 + `GET/POST/DELETE /api/channels`）
- [x] Devices REST API（`GET /api/devices`），前端 DevicesPage 动态加载
- [x] 知识库上传 API 前后端对齐（`POST /api/knowledge/documents/upload` multipart + `GET /api/knowledge/documents` + `DELETE /api/knowledge/documents/{id}` + `POST /api/knowledge/search`）
- [x] 记忆系统 REST API（`/api/memory/` 完整 CRUD）
- [x] Android 客户端（ChatScreen + Settings + 多语言 + SSE 流式，完整可用）

### Phase 7：飞书 / 企微原生工作流（重新聚焦）

#### 战略定位

让 OpenAgentic Workflow DAG 与飞书 / 企业微信原生工作流双向打通，覆盖中小企业最真实的业务编排场景：审批流、多维表格联动、群消息触发、人工审批、定时报表。

**不做泛连接器**（HTTP / SMTP / 钉钉 / 邮件 / 文件系统等留作社区贡献或客户付费定制）——聚焦飞书+企微做透，是与大厂生态绑定型 Agent 平台（火山+ArkClaw 等）形成差异化的核心战场。

#### 交付路径：CLI 优先

- **P0/P1 阶段全部用 CLI 跑通并验证**：通过 `openagentic` CLI + 飞书/企微独立运行脚本调试 workflow，不依赖 Web UI
- **可视化编辑器（React Flow）严格留在 P1 后段**——避免精力被前端工程拉走
- 所有新节点类型必须先有 CLI 调用样例与单元测试，再考虑前端接入

#### 新增节点类型

| 节点 type | 子动作 | 用途 |
|---|---|---|
| `feishu` | `send_msg` / `send_card` / `bitable_read` / `bitable_write` / `doc_read` / `doc_write` / `calendar_create` / `cli` | 飞书全能力节点，统一调 lark-cli 22 模块 |
| `wecom` | `send_msg` / `send_card` / `cli` | 企微全能力节点 |
| `approval` | provider: `feishu` / `wecom` | 触发飞书/企微原生审批 → run 进 suspended → 等回调 |
| `human_input` | provider: `feishu` / `wecom` | 发卡片让指定用户填表单 → 等卡片提交 → 写回 nodes.<id> |
| `subflow` | — | 一个 workflow 调用另一个 workflow（审批模板复用必需） |

#### DAG 引擎核心改造

**P0 必做**

| 任务 | 说明 |
|---|---|
| Run 状态机加 `suspended` | `pending → running → (suspended → running)* → completed/failed/cancelled` |
| 节点级挂起 | `approval` / `human_input` 节点声明 `_waiting_for: {type, instance_key, callback_url}` 写入 `node_states`，runtime 把 run 置为 suspended，释放 worker |
| 唤醒接口 | `POST /api/workflow-runs/{run_id}/resume`（内部接口，由飞书/企微事件 dispatcher 调用） |
| 事件触发器 | `extensions/channels/` 接收飞书审批回调 / 卡片提交 / 多维表格变更 → 反查 `_waiting_for` 命中的 run_id → resume |
| `WorkflowTrigger` 表 | 把"飞书事件 → 启动 workflow"做成数据，不写死代码 |
| 同层并行执行 | `asyncio.gather` 同入度=0 节点并行（批量发消息/批量写多维表格必需） |

**P1 重要**

| 任务 | 说明 |
|---|---|
| 子工作流节点（`subflow`） | 审批/通知模板沉淀为可复用子流 |
| Workflow 模板库 | 先做 10 个真场景模板（采购审批 / 月度报表 / 客户工单 / 合同会签 / 入职 SOP / 离职流程 / 周报汇总 / 客户回访 / 数据告警 / 知识问答） |
| `branch` / `loop` 节点 | 显式分支与有界循环 |
| SSE / WebSocket 流式 trace | 前端实时看节点状态（同时也给 CLI 用） |
| 可视化编辑器（React Flow） | 严格 P1 后段，不优先 |

**P2 锦上添花**

| 任务 | 说明 |
|---|---|
| 版本管理 + 灰度 + 回滚 | workflow_v1/v2 + 路由策略 |
| 节点级 SLA + 飞书告警 | Prometheus 扩到节点维度；告警发到飞书指定群 |
| Run 级 retries | 整图重跑（幂等性由用户保证） |
| 节点输入/输出 schema 声明 + 校验 | 当前 config 是裸 dict |
| 调度器（cron / event trigger） | 当前只能手动 POST run |
| 同 workflow 并发控制 | 当前一个 workflow 可同时多 run，无锁 |
| Trace 持久化分离 | 现在 trace 写在 `node_states` 一个 JSONB |

#### 数据库改动（最小化）

```sql
-- 新增：触发器映射
CREATE TABLE workflow_triggers (
  id UUID PRIMARY KEY,
  workflow_id UUID REFERENCES workflows,
  trigger_type VARCHAR(32),  -- 'feishu_approval' / 'feishu_bitable_change' / 'wecom_msg' / 'cron' ...
  trigger_config JSONB,       -- {"app_token": "xxx", "table_id": "yyy"}
  user_id UUID REFERENCES users,
  enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

`workflow_executions.node_states` 现有 JSONB 字段直接承载 `_waiting_for: {type, instance_code, node_id}`，**不加新列**。

#### 不做（明确放弃，避免膨胀）

- HTTP / 数据库连接器 / SMTP / 钉钉 / 邮件 / 文件系统等泛连接器 → 留给社区贡献或客户付费定制
- 复杂 BPMN 标准（XML 那套）→ 用更轻的 DAG + 节点类型
- 跨工作流复杂事务 / Saga → 第一阶段用最终一致性
- 实时流（Kafka 接入）
- Jinja / 表达式引擎 → 模板渲染保持「字符串替换」级别，复杂逻辑走 `tool` 节点

#### 已落地

- ✅ 条件边（消费 `EdgeDefinition.condition`）—— 支持 `==` / `!=` / 真值判断，跳过路径写入 trace
- ✅ `ExecutionStatus.suspended` 状态 + `TERMINAL_STATUSES` 终态集合（`models.py`）
- ✅ 挂起信号槽：`_waiting_for` / `_resume_payload` 两个 key 约定 + 6 个 helper，均操作 `node_states` JSONB **不加列**
- ✅ DB 迁移 `add_suspended_workflow_status` — 防御性兼容两个枚举名
- ✅ Runtime 挂起（1.2）：`_execute_definition` 检测挂起信号 → `set_waiting_for` + 持久化 outputs/trace → `run.status = suspended` → return early
- ✅ `execute_run` 适配 suspended（不设 `completed_at`、不覆盖 `node_states`）
- ✅ `feishu` 节点 — 包装 `lark-cli`（`subcommand` + `args`，支持 `{{input.x}}` / `{{nodes.x}}` 模板渲染）
- ✅ `wecom` 节点 — 包装 `wecom-cli`
- ✅ 45 条 workflow 测试（原 28 + 新增 17）
- ✅ System-Seed 预设工作流（`presets.py` + 3 个 YAML + lifespan upsert + `list_workflows` 合并系统/用户集）
- ✅ 并发治理底座 `ConcurrencyGate`（`concurrency/gate.py` + `limiter.py` + `config.py`）
- ✅ sender context 注入（`contextvars` → `input_data.context`，飞书/企微触发时自动写入）
- ✅ channel_runner 预设提示（LLM 看到"新闻周报"等关键词自动调 `run_workflow(slug)`）

#### 引擎改造 TODO（2026-04-29）

| # | 任务 | 优先级 | 文件 | 说明 |
|---|------|--------|------|------|
| 1 | `POST /api/workflow-runs/{id}/resume` 接口 | P0 | `router.py` | 写 `_resume_payload` + 调 `execute_run`（resume 模式） |
| 2 | `_execute_definition` resume 模式 | P0 | `service.py` | 从 `_outputs` 恢复已执行节点、从 `_waiting_for` 定位挂起节点、`pop_resume_payload` 作为节点输出、`clear_waiting_for` 后继续拓扑序 |
| 3 | `execute_run` resume 检测 | P0 | `service.py` | `run.status == suspended` 时跳过 `node_states` 重置、只改 status 回 `running` |
| 4 | 事件触发器反查 | P0 | `extensions/channels/` | 飞书审批回调 / 卡片提交 / 企微消息 → 按 `instance_key` 反查 `_waiting_for` 命中的 run → 调 resume 接口 |
| 5 | `WorkflowTrigger` 表 + CRUD | P0 | `models.py` + `router.py` | 新表 `workflow_triggers`（字段见上文数据库改动），CRUD API：`POST/GET/DELETE /api/workflow-triggers` |
| 6 | `approval` 节点真正发飞书审批 | P1 | `service.py` | 当前只返回挂起信号，需真正调 `lark-cli approval` 创建审批实例 + 记录 `instance_key` |
| 7 | `human_input` 节点真正发卡片 | P1 | `service.py` | 当前只返回挂起信号，需真正发飞书/企微交互卡片 + 等回调 |
| 8 | 同层并行执行 `asyncio.gather` | P1 | `service.py` | 同入度=0 节点并发，批量发消息/批量写多维表格必需 |
| 9 | `subflow` 节点 | P1 | `service.py` + `models.py` | 一个 workflow 调用另一个，审批/通知模板复用 |
| 10 | 10 个 Workflow 模板 | P1 | `templates/` 或 DB seed | 采购审批/月度报表/客户工单/合同会签/入职SOP/离职流程/周报汇总/客户回访/数据告警/知识问答 |
| 11 | SSE/WebSocket 流式 trace | P1 | `router.py` | 前端/CLI 实时看节点状态 |
| 12 | 可视化编辑器（React Flow） | P1 | `ui/` | 严格留到最后，不优先 |

### 四层记忆 → DB 版（未来）

- [ ] CoreMemory / Episode / Procedure 迁移到 PostgreSQL + pgvector
- [ ] 语义检索（768-dim，IVFFlat cosine）
- [ ] 时间衰减 + 重要性加权排序

## 开发与测试

```bash
# 全量测试（295 passed, 2 skipped）
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

### 测试目录结构

| 目录 | 说明 |
|------|------|
| `tests/cli/` | CLI 编码、slash 命令、交互边界 |
| `tests/concurrency/` | 并发网关（ConcurrencyGate）单元测试 |
| `tests/db/` | 数据库会话测试 |
| `tests/observability/` | 日志、指标、中间件测试 |
| `tests/skills/` | Skill 加载器与管理器测试 |
| `tests/tenant/` | 租户 contextvar 测试 |
| `tests/smoke/` | Phase 0 运维烟雾（需 Docker） |
| `tests/agent/` | Agent API 与服务边界测试 |
| `tests/core/` | 认证、聊天、LLM 边界测试 |
| `tests/knowledge/` | 知识库 API、搜索、服务测试 |
| `tests/mcp/` | MCP 客户端边界测试 |
| `tests/memory/` | 记忆管理器测试 |
| `tests/migrations/` | Alembic 迁移脚本正确性测试 |
| `tests/workflow/` | Workflow API、服务、runtime、suspended 状态测试 |
| `tests/` 根 | 配置、依赖注入、入口、健康检查 |

## 常见问题

1. **数据库连不上**：检查 `DATABASE_URL`，确认 Postgres 容器 healthy
2. **表不存在**：生产环境走 `alembic upgrade head`；开发环境 `APP_ENV=development` 可用 `create_all`
3. **SSE 被代理缓冲**：Nginx 需 `proxy_buffering off`
4. **模型 401/429**：核对 API Key；限流时 LiteLLM 自动重试
5. **`ModuleNotFoundError: No module named 'openagentic'`**：未 `pip install -e .`，在仓库根目录执行后重试
6. **`openagentic` 命令找不到**：同上，或直接用 `python -m openagentic.cli`
7. **pip 提示 `Ignoring invalid distribution ~...`**：删除 `.venv/lib/site-packages` 中以 `~` 开头的损坏目录后重装

## 隐私政策

OpenAgentic 以隐私优先为设计原则。

### 数据收集

**OpenAgentic 不收集、不上传、不遥测任何用户数据。** 项目不含任何埋点、分析 SDK、崩溃报告或使用统计收集逻辑。

### 数据存储

- 所有数据（对话记录、Agent 配置、知识库、记忆）仅存储在用户自有的 PostgreSQL 数据库中
- API 密钥、飞书 App Secret 等凭据仅存储在用户本地的 `.env` 文件和 `.openagentic/model_providers.json` 中，均被 `.gitignore` 排除
- 四层记忆系统存储在 `~/.openagentic/memory/`（本地文件系统）

### 飞书渠道

- 飞书机器人通过 WebSocket 长连接直接对接飞书官方服务，不经过任何第三方服务器
- 消息处理全程在用户自有服务器完成，消息内容不会被转发或存储到外部系统
- Agent 身份准则内置隐私铁律：**绝对禁止在自我介绍或任何回复中透露搭建者姓名、个人信息、服务器配置、部署位置**

### 责任边界

- OpenAgentic 是自部署软件，用户对其部署环境中的数据安全和访问控制负全责
- 建议定期轮换 API 密钥和飞书 App Secret
- 若将实例开放给第三方使用，请自行建立用户隐私协议

### 开源承诺

本项目以 Apache 2.0 许可证开源，所有代码可审计。隐私政策的变更将在本文件中体现。

---

## 贡献指南

欢迎贡献！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解代码规范、提交 PR 流程与行为准则。简要概览：

- **分支策略**：从 `main` 拉 feature 分支，提交前跑全量测试与静态检查
- **代码规范**：Python（Ruff + MyPy）、前端（ESLint + Prettier）
- **测试要求**：新增功能需附带测试；pytest 全量 295 条必须通过
- **PR 流程**：描述清楚改了啥、为什么、如何验证；CI 绿灯后请求 review
