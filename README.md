# OpenAgentic

**企业级 Agent 平台 · 中国可私有化部署 · AI 原生 SOP 工作流编排**

不是又一个 Claude Code 克隆。不是又一个多 LLM 路由器。是把「开发者 CLI + 业务 API + 工作流引擎 + 知识库」收敛到同一份私有化部署里，给一个组织用的 Agent 中台。

| 资源 | 链接 |
|------|------|
| 官网 | [openagentic-ai.github.io](https://openagentic-ai.github.io) |
| 仓库 | [github.com/openagentic-ai/open-agentic](https://github.com/openagentic-ai/open-agentic) |
| 许可证 | MIT |

## 产品定位

### 一句话

**Claude Code 是开发者工具，n8n 是工作流工具，OpenAgentic 把两者能力收敛到一份私有化部署里，外加「中国可用 + 行业 SOP 模板」。**

### 四个入口、一套后端

| 入口 | 谁用 | 解决什么 |
|---|---|---|
| **CLI** | 开发者 / 内部技术人员 | 终端协作（对标 Claude Code 但**仅补"行业基线"**，不追平 70+ 命令） |
| **HTTP REST API** | 业务系统 / 集成商 | 把 Agent 能力嵌进现有 IT 系统 |
| **Workflow 引擎** | 业务 / 运营人员 | 把企业 SOP 编排成 AI 流水线（DAG + 连接器 + 审批） |
| **Knowledge Base / RAG** | 知识员工 | 私有数据问答 + 检索增强 |

四个入口共用同一套：多租户隔离 / 审计日志 / 多 provider 路由 / 可观测性 / 文件式四层记忆。

### 我们是什么

**大厂的 Agent 是把"它的能力"装到客户面前；OpenAgentic 是把"客户的 SOP"装在中间，谁的能力都能调。**

### 为什么不是大厂 Agent

大厂 Agent 的本质——**"以我为中心"**：

- 字节 ArkClaw → 飞书优先、豆包优先、火山引擎优先
- 阿里 Agent → 钉钉优先、通义优先、阿里云优先
- 腾讯 Agent → 企微优先、混元优先、腾讯云优先
- 百度 Agent → 文心优先

但真实企业呢？一家公司可能：内部沟通用钉钉，和供应商对接用企微，和外资合作用飞书，给政府报告用邮件，同时用着阿里云 ECS、字节 CDN、腾讯 IM。**没有一家企业活在单一生态里。**

大厂 Agent 解决的是"我家生态内部的效率"，企业最痛的恰恰是**"跨生态的 SOP 串联"**——这是大厂出于本能不会做好的事，因为做好了等于让客户出生态。

OpenAgentic 是**中立的企业 SOP 编排层**——飞书/钉钉/企微/邮件/Webhook 全接，谁的能力都调，不站任何一家队。「中立」本身就是卖点：**我的 SOP 不被任何大厂绑架。**

### 我们不是什么

- **不是 Claude Code 的克隆**——CLI 是入口之一，只补"行业基线能力"，不追平命令数
- **不是 LLM 路由器**（LiteLLM / OneAPI 已经做了）——多 provider 是手段不是卖点
- **不是 SaaS**——核心交付形态是**私有化部署**
- **不是 2C 产品**——0 到 1 阶段不打消费市场
- **不站任何生态的队**——OpenClaw/ArkClaw/Linclaw/QClaw/DuClaw/MiClaw/CoPaw/Xiaoyi Claw 都是站某个生态/某个底座的队。OpenAgentic 是**「我谁都不站」**

### 目标客户画像

**通用市场**：**任何有标准化 SOP 的行业都是战场**——政府、金融、制造、物流、医疗、零售、能源、教育、咨询……只要业务有"流程"两个字，AI 就能渗透。

**典型客户特征**（不分行业）：
- 数据敏感 / 合规要求高 / 必须私有化部署
- 现有 IT 系统众多，业务流程已成型，要在原系统上加 AI 而非重做
- 想用 AI 但不能把数据和业务发给境外 SaaS

**典型用例**（跨行业）：
- 审批 / 报告 / 数据处理 / 合规审查 / 工单分流等 SOP 用 AI 加速 50%+
- 内部知识库 + 业务系统接口的统一 Agent 入口
- 替代部分外包人力（数据标注、报告撰写、初审、初级客服）

**首批共建客户来源**（节奏问题，不是定位问题）：
- 优先选 SOP 痛点显著、合规私有化要求高、有真实触达渠道的行业切入
- 沉淀首批客户案例后横向打开其他 SOP 密集行业

### 核心差异化（vs 主要竞品）

| 维度 | Claude Code | OpenClaw 类<br>（CLI 克隆） | **ArkClaw**<br>（字节） | n8n / Dify | **OpenAgentic** |
|---|---|---|---|---|---|
| 产品形态 | 开发者 CLI | 开发者 CLI | 飞书生态 Agent | 工作流平台 | **平台**（CLI + API + Workflow + KB） |
| 生态立场 | 中立 | 中立 | **飞书/豆包/火山引擎优先** | 中立 | **中立——谁都不站** |
| 中国可用 | ❌ 模型境外 | ⚠️ 模型自带 | ✅ 飞书深度集成 | ⚠️ 部分有限 | ✅ 接 DeepSeek / Qwen / Doubao / 私有 Ollama |
| 私有化部署 | ❌ | ✅ | ❌（SaaS 绑定） | ✅ | ✅ |
| 跨 IM 通道 | ❌ | ❌ | ❌（仅飞书） | ⚠️ | ✅ 飞书/钉钉/企微/邮件/Webhook 全接 |
| 多租户 | ❌ | ❌ | ⚠️（飞书租户体系） | ✅(SaaS) / ❌(自托管) | ✅ 行级隔离 + tenant context |
| AI 原生工作流 | ⚠️ | ❌ | ⚠️（飞书审批流） | ⚠️(加 LLM 节点) | ✅ DAG + 模板渲染 + 工具 + RAG 一体 |
| 行业 SOP 模板 | ❌ | ❌ | ❌ | ⚠️(通用) | 🚧 通用原型 + 行业模板共建 |
| 多 provider | ❌(仅 Claude) | ⚠️ | ❌（仅豆包） | ⚠️ | ✅ 20 个 |
| Skills / SOP 复用 | ✅(创新) | ⚠️(克隆) | ❌ | ⚠️ | ✅ Claude Code 风格 SKILL.md |
| 客户自由度 | 高 | 高 | **低（锁定飞书生态）** | 高 | **高（不锁任何生态）** |

**vs OpenClaw 类**：差异是**「平台 vs 工具」**。OpenClaw 装进客户内网还是开发者终端工具；OpenAgentic 装进客户内网是 Agent 中台——CLI 给开发者、HTTP 给业务系统、Workflow 给运营、KB 给知识员工，**一份部署服务整个组织**。

**vs n8n / Dify**：n8n 是把 LLM 当成工作流的一个节点；OpenAgentic 是**整体 AI 原生**——RAG / Agent / Workflow / Memory 共享语义层，不是事后拼接。

### 当前底气评估（对客户必须诚实）

| 能力 | 状态 | 对客户的话 |
|---|---|---|
| 私有化部署 | ✅ Docker Compose 一条命令起 | 真能部署，已验证 |
| 多 provider | ✅ 20 个 | 接得动主流模型 |
| RAG | ✅ pgvector + 重排 | 基础可用 |
| Workflow DAG 引擎 | 🟡 引擎在，连接器空 | **平台架子有，业务节点还得手填** |
| 多租户 | 🟡 行级隔离，Org 级未做 | 单组织 OK，多组织共享一份待补 |
| 行业模板 | ❌ 空 | **0 模板，第一个客户必须共建** |
| 人工审批节点 | ❌ 无 | 当前不能做需要审批的 SOP |
| 可视化编辑器 | ❌ 无 | 当前业务人员改不动工作流 |
| 节点连接器（HTTP/飞书/钉钉/企微/DB/邮件） | ❌ 无 | 当前只能调 LLM 和内置工具 |

**销售层规则**：上面 ❌/🟡 必须诚实告诉客户，不吹。0 到 1 阶段，**第一个客户就是产品的合伙人**——共建模板、提需求、踩坑、协议 6 个月共创。

### 战略主轴（路线判断）

#### 核心立场：中立编排层

**OpenAgentic 不站任何大厂生态。** 飞书/钉钉/企微/邮件/Webhook 全接，谁的能力都调。大厂 Agent 是"以我为中心"把自家能力装到客户面前；OpenAgentic 是把客户的 SOP 装在中间——客户用什么 IM、用什么云、用什么模型，我们接什么。这是认知差异化，也是 Phase 7 连接器的战略意义。

#### 双线并进

- **底座线（CLI 验证）**：用 CLI 把 Agent + Workflow + KB + Memory + 多 provider + 工具调用的完整范式**先跑通**。底座稳了，往后推平台基本不用回炉。
- **平台线（Workflow 企业化）**：底座稳定后投入主力做企业级能力（连接器、审批、模板、可视化、版本回滚），这是真正的护城河。

#### 优先级排序（按差异化护城河强度）

1. **Phase 7 — Workflow 企业化**（主轴）：**飞书/钉钉/企微/邮件/Webhook 全接，不偏不倚** + 审批节点 + 模板库 + 可视化 + 版本+回滚。**别人不做、客户真要、你能做**的赛道。中立编排层的工程落地。
2. **Phase 8 — 行业 SOP 模板库**（横向扩张）：**任何有 SOP 情景的行业都做**。首批靠最熟领域共建沉淀通用原型，再横向复制到金融/制造/物流/医疗/零售/教育等任意 SOP 密集行业。
3. **Phase 5.5 — CLI 补行业基线**（辅线，但**底座验证场**）：仅做"不做就 broken"的命令（`/compact` `/context` `/cost` `/permissions` `write_file diff`）。**真正价值在于**用 CLI 验证 Agent+Workflow+KB+Memory 范式跑得通，70+ 命令对标已放弃。
4. **Phase 6 — 前后端闭环 / Android**（暂缓）：CLI 优先，UI/Android 等首批客户共建后由真实需求驱动。

## 最近更新

- **237 passed, 2 skipped** 测试覆盖（新增 75 条）
- 新增测试模块：`tests/db/`、`tests/observability/`、`tests/skills/`、`tests/tenant/`、`tests/config/`、`tests/deps/`、`tests/entry/`
- 全量源文件中文行内注释补全

## 目录

- [产品定位](#产品定位)
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
| **5 多租户+可观测** | ✅ 单租户级 | 行级 user_id 隔离 ✓；tenant/request_id contextvar ✓；Prometheus `/metrics` ✓；structlog 注入 request_id+tenant_id ✓。组织(Org)级隔离与跨服务 correlation 留作未来扩展，**计费/配额已撤回（属上游 LLM 网关职责）** |
| **5.5 CLI 补行业基线**（辅线） | 🟡 推进中 | 已落地：`/compact` `/context` `/btw` + procedural 自动注入 + **P0 三件**（`/cost` / `write_file` diff / `/permissions`）；待做（P1）：`/diff` / `/review` / 3 个内置 SKILL；70+ 命令对标已**克制放弃** |
| **6 前后端闭环 / Android** | ⏸ 暂缓 | UI 8 页面完成；Devices/Sessions/Channels 后端 stub；Android 仅图标接入；等客户共建后再补 |
| **7 Workflow 企业化**（主轴） | 🔲 计划中 | **核心差异化护城河**：节点连接器 / 人工审批 / 模板库 / 可视化编辑器 / 版本+回滚 / 节点级 SLA |
| **8 行业 SOP 模板**（横向扩张） | 🔲 计划中 | **任何有 SOP 情景的行业都做**；通用原型：审批型 / 报告生成 / 分类路由 / 质检合规 / 流水线处理 |

> **战略主轴（2026-04-26 调整）**：差异化护城河在 Phase 7（Workflow 企业化）+ Phase 8（行业 SOP 模板）。CLI 是辅线，仅补"行业基线能力"（不做就 broken 的部分），不再追平 Claude Code 70+ 命令。
> Android 客户端骨架在 `extensions/android/`，仅完成应用图标接入（mipmap 5 档密度 + adaptive icon + 白底），无功能实现。

### 已知 Web 端缺口（暂不修）

- `POST /api/knowledge/documents/upload` 前端调用、后端不存在（前端期望默认 KB+文件 multipart，后端要求 `kb_id`+JSON 文本）
- Skills 页面 169 行 UI 就绪，无任何后端 CRUD
- Devices/Sessions/Channels 后端为 Stub 或空
- 记忆系统未暴露到 FastAPI（仅 CLI 可用）

### CLI 当前能力

- **20 个 LLM provider**：OpenAI / Anthropic / DeepSeek / XAI / Gemini / Mistral / Cohere / Groq / OpenRouter / Moonshot / Zhipu / MiniMax / Volcengine / Baidu / Tencent / Nvidia / Together / Fireworks / Qwen / Ollama
- **12 个工具**：`run_command` `read_file` `write_file` `delete_file` `done` + 7 个 memory 工具
- **17 个 slash 命令**：`/model` `/providers` `/automodel` `/clear` `/login-platform` `/skills` `/compact` `/context` `/btw` `/cost` `/permissions` 等
- **Skills 系统**（Claude Code 风格）：`~/.openagentic/skills/<slug>/SKILL.md`，frontmatter+markdown，启动时 metadata 注入 system prompt（每条 ~50 token），全文按需 `read_file` 加载。内置 3 个：`git-commit` / `code-review` / `debug-trace`。`/skills` 列表，`/skills <name>` 看详情，`/skills new <name>` 建模板，`/skills reload` 热加载
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
- **Phase 5.5 P0 三件**全部落地：`/cost`（per-model token+USD）、`write_file` 覆盖时 unified diff 预览、`/permissions`（allow/ask/deny + 路径/前缀白/黑名单）
- **root 命令强制确认**：`sudo` / `doas` / `pkexec` / `su` token 级匹配（避免 `sudoku` 误伤），即使 policy=allow 或命中 allow_prefixes 也强制 Y/N
- **代码瘦身**：`repl.py` 949 → 434 行，提取 `cli/slash_commands.py`（567 行）承接所有 `_handle_*` 处理器与 UI 原语；`main_loop` 535 → 408 行，`_execution_consumer` 325 → 198 行，全项目 .py 文件均 ≤ 800 行

### 测试覆盖

237 passed, 2 skipped — 覆盖 CLI 编码、P0 三件（`/cost` / `write_file` diff / `/permissions`）、root 命令强制确认、LLM provider 配置、记忆系统、知识库、工作流、MCP、Agent、认证、聊天、迁移脚本、运维烟雾、数据库会话、可观测性、Skills 系统、租户上下文。

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
├── skills/              # CLI skills（Claude Code 风格 SKILL.md，含 builtin/）
├── tenant/              # 请求级 tenant_id / request_id contextvar
├── observability/       # structlog 配置 + Prometheus + RequestContextMiddleware
└── db/                  # session、Base
ui/                      # React 前端
extensions/
└── android/             # Android 客户端（已接入应用图标 mipmap 5 档+adaptive，当前暂缓）
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

### P1/P2 待办（已合并入 Phase 5.5）

→ 见下方 [Phase 5.5：CLI 对标 Claude Code](#phase-55cli-对标-claude-code)

### Phase 5：多租户 + 可观测

- [x] 行级 `user_id` 隔离（已存在于 db schema）
- [x] 请求级 tenant context（`tenant/` contextvar，`tenant_id == user_id`）
- [x] Prometheus `/metrics`（method/path_template/status 三维标签，`/health` `/metrics` 自身排除）
- [x] structlog 自动注入 `request_id` 与 `tenant_id`，`X-Request-ID` 中间件透传/生成
- [ ] 组织(Org)级隔离（需新表 `organizations`、`user_organizations`，全路由 scope 改造，大改动，按需启动）
- [ ] 跨服务 correlation（LiteLLM 调用、DB query 注入 request_id；目前仅 HTTP 入站层）
- ~~用量统计 / 计费 / 配额~~（已撤回——属上游 LLM 网关 / LiteLLM Proxy 职责，agent 应用层不重复造）

### Phase 5.5：CLI 对标 Claude Code（已重新分类，辅线）

> **战略调整（2026-04-26）**：放弃 70+ 命令对标。Claude Code 的命令分三类对待——**行业基线 / 风格选择 / 打不过 + 低价值**。CLI 是辅线，主轴投入 Phase 7。

#### A. 行业基线（不做就 broken，必做）

| 任务 | 状态 | 优先级 | 备注 |
|---|---|---|---|
| `/compact` `/context` `/btw` | ✅ | — | 已完成（D1 简单组） |
| Procedural memory 自动注入 ReAct | ✅ | — | 已完成（镜像 episodic） |
| `/cost` | ✅ | — | 已落地：per-model token + USD 估算（litellm.completion_cost），`/clear` 自动重置 |
| `write_file` diff 预览（覆盖时 unified diff） | ✅ | — | 已落地：覆盖时在 confirm 提示中展示 unified diff（>80 行截断，二进制降级） |
| `/permissions`（allow/ask/deny + 路径白名单） | ✅ | — | 已落地：4 个 gated tool（read/run/write/delete），`~/.openagentic/permissions.json`，路径与命令前缀双白/黑名单 |
| `/diff`（包 `git diff` + rich 染色） | 🔲 | P1 | 半小时活 |
| `/review`（喂 git diff + code-review skill） | 🔲 | P1 | 1 小时活 |
| 3 个内置 SKILL：`security-review` / `simplify` / `batch` | 🔲 | P1 | 写 SKILL.md，下次启动自动播种 |
| 全套烟测（所有新命令 + 3 SKILL 通过 LLM 触发验证） | 🔲 | P2 | 收尾 |

#### B. 风格选择（Claude Code 的具体设计，不一定最优）

| 任务 | 决策 | 理由 |
|---|---|---|
| `/copy` | ❌ 不做 | 终端自带复制（鼠标选择 / Cmd+C），重复造轮子 |
| `/plan` | ❌ 不做单独命令 | 做成 `planner` SKILL 更优雅，避免命令膨胀 |
| `/resume` `/rename` `/branch`（会话持久化） | 🔲 重新设计 | **不学** Claude Code 的 SQLite 方案，沿用文件式（一致 episodic 那套），更轻 |

#### C. 推迟（CLI 用户低频，资源转 Phase 7）

- `/memory` `/export` `/debug`（CLI nice to have，不影响交付）
- `/agents` `/mcp`（HTTP 模块对接，CLI 高频度低）

#### D. 不做（打不过 / 不适用 / 商业化无关）

- 跨端联动：`/desktop` `/mobile` `/chrome` `/teleport` `/remote-control`
- 商业化：`/upgrade` `/passes` `/extra-usage` `/stickers`
- 第三方集成：`/install-github-app` `/install-slack-app` `/web-setup`
- 基础设施大工程：`/sandbox` `/heapdump` `/doctor`
- 依赖未建系统：`/loop` `/rewind`（需 checkpoint 系统）
- 多模态：`/voice`
- 行为类（`/batch` `/simplify` `/security-review` `/debug` 等）→ **统一走 SKILL.md 路线**，不做硬编码 slash

#### 已完成（Phase 5.5 累计）

- [x] `/skills` 命令 + Skills 系统（Claude Code 风格 SKILL.md，3 个内置）
- [x] Ctrl+C 中断单轮 react（保留会话）
- [x] `--no-provider-check` 跳过 API key 强制配置向导
- [x] `/compact` `/context` `/btw` 三命令
- [x] Procedural memory 自动注入

### Phase 7：Workflow 企业化（主轴 / 核心差异化）

> **战略意义**：差异化护城河的真正来源。从「平台架子」走到「企业可用」。这是别人不做、客户真要、你能做的赛道。
>
> **判断**：CLI 路线（Phase 5.5）做完基线即克制。资源主投到这里。

#### 核心能力清单（按优先级）

| 任务 | 优先级 | 说明 | 验收 |
|---|---|---|---|
| **节点连接器** | **P0** | HTTP / 数据库（PG/MySQL/MongoDB）/ SMTP / **飞书** / 钉钉 / 企微 / 邮件 / Webhook / 文件系统 | 没连接器=玩具，必须先做；所有 IM 通道平等对待，不偏不倚 |
| **人工审批节点** | **P0** | 工作流暂停 → 通知（钉钉/企微/邮件）→ 用户操作 → 继续 / 终止 | 企业 SOP 必有人工，无审批=不能上业务 |
| **数据流串联**（KB ↔ Workflow ↔ Agent） | **P0** | 节点可读写 KB；Agent 可被 Workflow 调；Workflow 输出可入 KB | AI 流水线整体性的体现 |
| **Workflow 模板库** | P1 | 模板 = YAML + 配套 KB + 配套 SKILL，行业模板优先（见 Phase 8） | 沉淀 5-10 个可复用模板 |
| **可视化编辑器**（React Flow） | P1 | 业务人员能拖拽改流程，不用写 YAML | UI 层落地 |
| **版本管理 + 灰度 + 回滚** | P2 | workflow_v1/v2，企业上线必须可回滚 | 表设计 + 路由策略 |
| **节点级 SLA + 失败告警** | P2 | Prometheus 已有基础，扩到节点维度；告警接钉钉/企微 | 可观测性升级 |
| **重试 / DLQ 策略** | P2 | 节点失败后的处理选项（重试 N 次、转人工、DLQ） | 企业容错要求 |

#### 不做清单

- 复杂 BPMN 标准（XML 那套）→ 用更轻的 DAG + 节点类型
- 跨工作流复杂事务 / Saga → 第一阶段用最终一致性
- 实时流（Kafka 接入）→ 不是当前客户的高频痛点

### Phase 8：行业 SOP 模板库（横向扩张）

> **战略意义**：把"通用平台"变成"行业方案"。**任何有标准化 SOP 的行业都是战场**——这是 OpenAgentic 的应有之义，不要早早自我设限到某一个行业。
>
> **节奏**：与 Phase 7 并行。每完成一个 Phase 7 能力就立刻在某个模板上验证。**首批客户来源是节奏问题，不是定位问题**。

#### 候选行业（按 SOP 密集度，不分先后）

| 行业 | SOP 痛点示例 |
|---|---|
| **政府 / 公共数据** | 数据质量审查、报告撰写、合规出境审查、群众诉求工单分流 |
| **金融** | 反洗钱审查、信贷材料初审、合规报告生成、客户工单分类 |
| **制造** | 工单派发、QC 报告、供应商资质审查、设备故障初诊 |
| **物流 / 供应链** | 异常单据处理、报关材料审查、客户咨询自动化 |
| **医疗** | 初诊问诊辅助、医保审核、病历整理、文献查询 |
| **零售 / 电商** | 商品描述生成、客户工单、退换货初审、库存异常分析 |
| **能源 / 公用事业** | 工单调度、设备巡检报告、安全合规审查 |
| **教育** | 作业批改、学情分析、家长沟通自动化、教研材料整理 |
| **咨询 / 法律** | 合同初审、研究材料整理、报告草稿、法规变更追踪 |
| **任何"有 SOP 情景"的行业** | 见上面任意类比 |

#### 通用 SOP 模板原型（跨行业可复用）

每个模板 = Workflow YAML + 配套 KB + 配套 SKILL。

| 模板 | 通用结构 | 跨行业复用度 |
|---|---|---|
| **审批型 SOP** | 数据查询 → LLM 初审 → 人工复核 → 入库/打回/通知 | ★★★★★（金融审单 / 政府审批 / 合同审查 / 医保审核都是它） |
| **报告生成 SOP** | 数据查询 → 模板填充 → LLM 草稿 → 人工审批 → 推送 | ★★★★★（月报 / 周报 / 行业研究 / 项目汇报全适用） |
| **分类路由 SOP** | LLM 分类 → 路由规则 → 通知接收人 → 跟踪反馈 | ★★★★★（工单 / 邮件 / 投诉 / 群众诉求） |
| **质检 / 合规 SOP** | KB 查规则 → 数据比对 → LLM 报告 → 人工复核 | ★★★★（合规 / 质检 / 安全 / 数据合规） |
| **流水线处理 SOP** | 触发 → 多步处理 → 入库 → 通知 | ★★★（数据预处理 / 文档转换 / 批量任务） |

**抽象原则**：先沉淀**通用结构**（5 个原型覆盖 80% SOP 场景），再为每个行业做配套 KB + SKILL 的微定制。一份引擎，N 行业落地。

#### 首批共建客户路径（节奏）

- 优先选 SOP 痛点显著、合规私有化要求高、有真实触达渠道的行业切入
- 协议形式：6 个月共创，第一份模板共建
- 沉淀完毕后即横向打开金融 / 制造 / 物流 / 医疗 / 零售 / 教育 / 咨询等任意 SOP 密集行业
- **不限定行业不等于不聚焦**——聚焦"通用 SOP 原型 + 私有化部署 + 中国可用"，而非聚焦某一个行业

### Phase 6：前后端闭环 / Android（暂缓）

> **战略调整**：CLI 优先 + Workflow 优先。UI / Android 推到客户共建之后，由真实需求驱动。**工作流可视化编辑器（React Flow）已转 Phase 7**，那里才是它该在的位置。

#### 已完成
- [x] `ui/` 8 页面框架（Sessions、Settings、Skills、Channels、Devices 等）
- [x] CLI Skills 系统（文件式 Claude Code 风格，前端 SkillsPage 暂未对接）

#### 暂缓（等客户共建后再做）
- [ ] Devices / Sessions / Channels 后端（当前为 stub）
- [ ] 知识库上传 API 前后端对齐
- [ ] 前端 SkillsPage 接入 CLI Skills（需把后端 skills 暴露 HTTP API）
- [ ] Android 客户端功能实现（仅完成应用图标接入）

### 四层记忆 → DB 版（未来）
- [ ] CoreMemory / Episode / Procedure 迁移到 PostgreSQL + pgvector
- [ ] 语义检索（768-dim，IVFFlat cosine）
- [ ] 时间衰减 + 重要性加权排序
- [ ] `/api/memory/` REST API

## 开发与测试

```bash
# 全量测试（237 passed, 2 skipped）
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
| `tests/db/` | 数据库会话测试 |
| `tests/observability/` | 日志、指标、中间件测试 |
| `tests/skills/` | Skill 加载器与管理器测试 |
| `tests/tenant/` | 租户 contextvar 测试 |
| `tests/config/` | 配置加载与校验 |
| `tests/deps/` | FastAPI 依赖注入 |
| `tests/entry/` | CLI 入口参数解析 |
| `tests/smoke/` | Phase 0 运维烟雾（需 Docker） |
| `tests/` 根 | Agent、工作流、知识库、MCP、认证、聊天、记忆、迁移等 |

## 常见问题

1. **数据库连不上**：检查 `DATABASE_URL`，确认 Postgres 容器 healthy
2. **表不存在**：生产环境走 `alembic upgrade head`；开发环境 `APP_ENV=development` 可用 `create_all`
3. **SSE 被代理缓冲**：Nginx 需 `proxy_buffering off`
4. **模型 401/429**：核对 API Key；限流时 LiteLLM 自动重试
5. **`ModuleNotFoundError: No module named 'openagentic'`**：未 `pip install -e .`，在仓库根目录执行后重试
6. **`openagentic` 命令找不到**：同上，或直接用 `python -m openagentic.cli`
7. **pip 提示 `Ignoring invalid distribution ~...`**：删除 `.venv/lib/site-packages` 中以 `~` 开头的损坏目录后重装

## 贡献指南

欢迎贡献！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解代码规范、提交 PR 流程与行为准则。简要概览：

- **分支策略**：从 `main` 拉 feature 分支，提交前跑全量测试与静态检查
- **代码规范**：Python（Ruff + MyPy）、前端（ESLint + Prettier）
- **测试要求**：新增功能需附带测试；pytest 全量 237 条必须通过
- **PR 流程**：描述清楚改了啥、为什么、如何验证；CI 绿灯后请求 review
