# OpenAgentic

企业级 AI Agent 平台 — **Python（FastAPI）后端** + **React 前端**，面向 **私有化 / 内网** 部署：大模型对话以 **长期在线服务** 形态落在自有基础设施；会话与业务数据进 **自建 PostgreSQL**；模型调用通过 **LiteLLM** 统一对接多家厂商。多 Agent、工具编排、RAG、工作流等按 **Phase 路线图** 迭代，工程上预留 **权限与审计** 扩展位。

| 资源 | 链接 |
|------|------|
| **官网** | [openagentic-ai.github.io](https://openagentic-ai.github.io) |
| **代码仓库** | [github.com/openagentic-ai/open-agentic](https://github.com/openagentic-ai/open-agentic) |
| **许可证** | MIT |

---

## 目录

- [当前实现进度（与仓库代码一致）](#当前实现进度与仓库代码一致2026-04-核对)
- [项目背景与目标](#项目背景与目标)
- [已落地能力与实现手段（详述，七小节）](#已落地能力与实现手段详述七小节)
- [业务内容与模块范围](#业务内容与模块范围已实现--规划中)
- [技术模块详解（十小节）](#技术模块详解是什么--为何选型--解决什么问题)
- [规划能力总览（Phase 2–6）](#规划能力总览phase-26)
- [技术栈总览](#技术栈总览)
- [架构设计](#架构设计)（含逻辑简图、分层详解、仓库目录）
- [核心模块与 API 边界](#核心模块与-api-边界)
- [工程化与非功能需求](#工程化与非功能需求)
- [难点与取舍](#难点与取舍)
- [一次流式对话请求的完整生命周期](#一次流式对话请求的完整生命周期)
- [开发路线 Phase 0–6（Todo）](#开发路线-phase-06todo)
- [快速启动](#快速启动)
- [CLI 模式（直接对话）](#cli-模式直接对话)
- [API 端点](#api-端点)
- [前端 `ui/`](#前端-ui)
- [常见问题与排错](#常见问题与排错)
- [仓库与贡献](#仓库与贡献)
- [许可证](#许可证)

---

## 当前实现进度（与仓库代码一致，2026-04 核对）

> **说明**：下文「详述」章节保留 **设计意图、选型理由、面试可展开口径**；本表专门对齐 **当前仓库里真实写了什么**，避免简历与代码脱节。两者 **并存**：短表看进度，长文看深度。

| Phase | 状态 | 说明 |
|-------|------|------|
| **Phase 0** | **基本完成** | FastAPI 工厂、`lifespan`、Docker Compose（**`pgvector/pgvector:pg16`**）、健康检查、`core` 目录与依赖链、**`structlog` 已接入启动日志**（见 `main.py`）。 |
| **Phase 0 注意项** | **已完成** | Alembic revision `62da57f49c3e_initial_tables` 已补齐用户、会话、消息、Agent 与执行历史等建表逻辑；开发环境仍由 `create_all` 兜底，生产环境走 `alembic upgrade head`。 |
| **Phase 1** | **已完成** | 注册 / 登录 / **JWT**、会话与消息 **CRUD**、**LiteLLM** 调用、**SSE**（`StreamingResponse` + `text/event-stream`，见 `core/chat`）、**`ui/`** 前端与 Phase 1 API 协同。 |
| **Phase 2** | **基础版已完成** | 新增 `agent/` 与 `mcp/` 实现：Agent CRUD、最小 ReAct 执行器、工具注册表、MCP HTTP JSON-RPC 客户端、执行历史落库与 API。 |
| **Phase 3** | **已完成** | `workflow/` 已实现：Workflow CRUD、Run 执行与取消、DAG 校验与拓扑执行、节点重试/超时、变量模板渲染、运行轨迹与状态查询。 |
| **Phase 4** | **未实现（占位）** | `knowledge/` 目录已实现：文档上传、分块、向量存储、检索 API；数据库迁移 `add_knowledge_tables.py` 已就绪；与 Agent 集成通过 `knowledge_search` 工具 |
| **Phase 5** | **未实现（仅部分基建）** | 无完整多租户计费闭环、无 Prometheus **`/metrics`** 等；**`structlog` 已接入** 不等于「可观测性全套」。`tenant/`、`observability/` 多为占位。 |
| **Phase 6** | **部分** | **`ui/`** 已有多页面（Sessions、Settings、Skills、Channels、Devices 等）；Skills 页面已实现前端 UI 与静态数据，后端 API 待完善；工作流编辑器、知识库管理 UI 等 **与 Phase 4/5 后端能力逐步形成闭环** |

**与「详述」正文的阅读顺序建议**：先读本表建立 **事实边界**，再读 **「已落地能力与实现手段」** 与 **「技术模块详解」** 理解 **为什么这样设计、后续怎么演进**。

---

## 项目背景与目标

面向企业 **私有化部署** 场景：将大模型对话以 **可长期在线的服务形态** 部署在自有服务器与内网，覆盖 **客服、跟单、制度与内部知识库问答** 等常见业务。核心产品目标是 **安全可控** —— 业务数据与模型调用边界留在企业侧，降低将核心业务数据外泄到公网 SaaS 的风险。

当前阶段已落地 **统一账号、多会话管理**、对接 **100+ 厂商模型** 的 **流式对话**（通过 LiteLLM 统一网关），会话与业务数据写入 **自建 PostgreSQL**；多 Agent 协同、工具编排及基于业务数据的持续优化按 **产品路线图** 迭代，并在工程上预留 **权限控制与操作审计** 等治理要求。

**与实现的对应关系**：「账号 / 多会话 / 多厂商流式 / 自建库」分别由 **JWT + bcrypt、Conversation/Message REST、LiteLLM + SSE、Postgres + Compose +（Alembic 或开发态 create_all）** 等组合落地；路线图与治理预留的 **工程落点** 见下文 **「已落地能力与实现手段（详述）」**（分 7 个小节，含请求链、资源模型、流式形态、迁移与审计扩展位）。

---

## 已落地能力与实现手段（详述，七小节）

以下与 [open-agentic](https://github.com/openagentic-ai/open-agentic) 公开仓库及典型 **FastAPI + LiteLLM** 落地方式对齐；若你本地分支有额外中间件，以代码为准。

### 1）统一账号：从注册到「带身份调用 API」

**接口与数据流**

- **注册**：客户端 `POST /api/auth/register` 提交用户名、密码等（具体字段以 OpenAPI `/docs` 为准）。服务端对密码做 **bcrypt** 哈希（不存明文），将用户行写入 **PostgreSQL**（SQLAlchemy 模型；**生产环境**以 **Alembic revision** 保证各环境表结构一致，见上文「Phase 0 注意项」）。
- **登录**：`POST /api/auth/login` 校验用户名密码；校验通过后使用 **python-jose** 按配置的 **签名算法与密钥** 签发 **Access Token**（及按需的 **Refresh Token** 策略）。JWT 载荷中至少包含 **`sub`（用户主键或稳定标识）**、`exp`（过期时间）等标准声明，便于后续所有受保护路由 **无状态** 验签。
- **刷新**：`POST /api/auth/refresh` 在 **滑动会话** 或 **双令牌** 策略下延长可用时间（实现细节以仓库为准），减少用户反复输密码。
- **当前用户**：`GET /api/auth/me` 通过 FastAPI **依赖注入** 从 `Authorization: Bearer` 解析 JWT，失败则 **401**；成功则返回用户档案，供前端展示昵称、头像扩展位等。

**工程上解决什么问题**

- **多租户之前的「单租户多用户」**：先保证 **人** 与 **数据** 绑定，后续再叠组织 / 角色不会推翻账号模型。
- **水平扩展**：无会话粘滞在单机内存，API 实例可多台部署（需共享同一验签密钥或使用非对称 JWT + JWKS 演进）。
- **安全基线**：密码哈希、HTTPS（部署层）、密钥不进仓库，满足内网交付的 **最低安全叙事**。

### 2）多会话管理：REST 资源模型 + 异步落库

**资源划分**

- **Conversation（对话）**：一级资源，`GET /api/conversations` 分页 / 列表（具体分页参数以代码为准）、`POST` 创建、`GET /api/conversations/{id}` 取详情、`DELETE` 删除。每条会话在库中带有 **所有者 `user_id`（外键）**、标题、时间戳等，保证 **只能操作自己的会话**（在路由或 service 层过滤）。
- **Message（消息）**：二级资源，挂在某 `conversation_id` 下：`GET …/conversations/{id}/messages` 拉历史；`POST …/messages` **发送新消息并触发模型**。这样前端可以 **会话列表 → 点进会话 → 消息时间线** 的产品结构，与 Slack / ChatGPT 类 UX 一致。

**持久化与一致性**

- 所有读写经 **AsyncSession**：在 `async def` 路由里 `await session.commit()` / `rollback()`，避免阻塞事件循环。
- **删除会话**时应在同一事务内 **级联删除消息**（或软删除），防止孤儿消息占空间、泄露历史。
- 为后续 **审计** 预留：消息表可扩展 **role（user / assistant / system）**、**token_usage JSON**、**model_name** 等列，便于按会话统计成本与回放。

**解决什么问题**

- **「只有一个全局聊天窗」**：企业场景需要 **按客户 / 按工单 / 按主题** 拆线程；会话模型是后续 **权限按会话、导出按会话** 的前提。
- **可追溯**：出问题时可以 **按 `conversation_id`** 拉全链路消息与当时选用的模型。

### 3）100+ 厂商模型：LiteLLM 作为统一网关层

**实现思路**

- 在 **`core/llm`**（目录名以仓库为准）封装对 **LiteLLM** 的调用：上层只传 **模型标识字符串**、**messages**、是否 **stream** 等，不关心底层是 OpenAI、Azure、Anthropic 兼容端还是国内厂商兼容端。
- **模型发现**：`GET /api/models` 将「当前环境可用的模型列表」暴露给前端下拉框；列表来源可以是 LiteLLM 配置、静态白名单或 **动态探测**（以实际实现为准）。
- **密钥与路由**：各厂商 **API Key、base_url** 放在 **环境变量或客户密钥管理系统**，由 Pydantic Settings 注入；避免把密钥写进前端或镜像层（除非构建参数由 CI 注入且镜像私有）。

**解决什么问题**

- **对接边际成本**：新厂商往往是 **加配置而非加分支**，符合平台型产品节奏。
- **故障隔离**：网关层可统一 **超时、重试、降级**（例如主模型失败回退到备用小模型 —— 策略可迭代）。
- **未来计费**：在网关统计 **每次调用的 input / output tokens** 写入表或日志，为 Phase 5 **按量计费** 埋点。

### 4）流式对话：SSE + 异步生成器

**协议与体验**

- **SSE**：`POST …/conversations/{id}/messages` 返回 `Content-Type: text/event-stream`（或框架等价物），正文为 **事件流**：每个 **delta** 携带模型新增文本片段，前端用 **EventSource** 或 `fetch` ReadableStream 消费。
- **后端形态**：FastAPI 侧通常返回 **`StreamingResponse`**，内部 **`async for chunk in llm_astream(...): yield format_sse(chunk)`**，把 LiteLLM 的 **异步流** 桥到 HTTP。
- **与 JWT 结合**：在 **建立流之前** 完成鉴权；流中途客户端断开时应 **取消上游生成**（`asyncio.CancelledError` 处理），避免白白消耗 token。

**解决什么问题**

- **首字延迟（TTFB）**：长回答不必等全文生成完才返回，显著改善 **体感速度**。
- **弱网场景**：用户可更早看到部分输出，减少「卡死重试」。

### 5）会话与业务数据写入自建 PostgreSQL

**部署拓扑**

- **Docker Compose** 中定义 **postgres** 服务（镜像版本钉死为 **16** 或客户认可版本）、**数据卷** 持久化 `/var/lib/postgresql/data`，应用服务通过 **服务名 DNS** 访问 `DATABASE_URL`。
- 应用镜像或本地进程通过 **`postgresql+asyncpg://...`** 连接，**连接池** 在 lifespan 中创建、在 shutdown 中关闭。

**Schema 与迁移**

- **Alembic**：每次改 ORM 模型后生成 revision，`upgrade` 应用到各环境；生产变更走 **评审 + 备份 + 窗口**。
- **pgvector**：以扩展形式 `CREATE EXTENSION IF NOT EXISTS vector`（具体迁移脚本以仓库为准），为 Phase 4 **向量列 / 向量表** 预留。

**解决什么问题**

- **数据主权**：对话与业务 **不出客户内网**（模型调用若走公网 API 则另签合规，与库分离讨论）。
- **可恢复**：备份恢复演练有明确对象（PG 实例）。
- **可演进**：从「只存消息文本」演进到「存 embedding、存 usage」不推翻存储选型。

### 6）路线图能力（多 Agent、工具编排、持续优化）：模块化预留

**代码与文档对齐**

- 仓库 `src/openagentic/` 下已拆分 **`agent/`、`workflow/`、`knowledge/`、`mcp/`** 等包，与 README **Phase 2–4** 一一对应：
  - **Phase 2**：Agent CRUD、**ReAct 循环**、工具注册表、**MCP Client**、执行历史。
  - **Phase 3**：JSON **DAG**、拓扑排序执行、节点间 **`{{var}}` 模板传参**。
  - **Phase 4**：文档上传、分块、嵌入、**pgvector** 检索、与 Agent / 工作流集成。
- **当前未实现的接口**（如部分 `GET /api/agents` 等）在 README 中诚实标注 **待实现 / 占位**，避免过度承诺；面试时可强调 **「先底座后智能体」** 的交付顺序。

**解决什么问题**

- **避免巨石类名混乱**：分包即 **限界上下文** 雏形。
- **降低后续集成 MCP 的成本**：协议与目录位已留，减少从 0 引入 MCP 时的目录大挪移。

### 7）权限控制与操作审计：工程预留的具体落点

**当前可做的「不推翻式」预留**

- **数据所有权**：会话、消息表强制 **`user_id`**，所有查询默认带 **`WHERE user_id = current_user`**，为后续 **RBAC** 叠加 **组织 ID** 留 JOIN 位。
- **JWT 声明扩展**：预留自定义 claims（如 `org_id`、`role`）的解析与校验函数，即使暂时不签发，也不在代码里写死「只有 sub」。
- **审计与观测（Phase 5）**：路线中包含 **structlog、correlation ID、Prometheus**；实现上可在中间件注入 **request_id**，在每次 LLM 调用前后打 **结构化日志**（用户、会话、模型、耗时、token，注意 **脱敏**）。

**解决什么问题**

- **等保 / 内审问答**：能说清 **谁在何时访问了哪类数据**，而不是「只有 nginx access log」。
- **事故归因**：出现越权或误调用时，有 **会话级** 与 **请求级** 线索。

---

## 业务内容与模块范围（已实现 / 规划中）

**已实现（与 Phase 0–1 对齐，细节以代码为准）**

- 应用脚手架：FastAPI 应用工厂、生命周期管理、健康检查。
- 数据层：PostgreSQL 16 + **pgvector 镜像**（关系数据与向量扩展一体化）、SQLAlchemy **2.0 异步** ORM、**Alembic 工程**（revision 需按环境维护）、**Pydantic Settings** 集中配置。
- 认证：**注册 / 登录 / JWT（python-jose）+ bcrypt**；对话 **CRUD**。
- LLM：**LiteLLM** 统一网关，对接 **100+ Provider**；对话 **SSE 流式** 返回。
- 前端：**React + Vite + TailwindCSS + Zustand** 管理端与对话界面，与后端 **REST + SSE** 协作。
- 交付：`docker compose` 拉起应用与数据库（含 **depends_on** 与 Postgres **healthcheck**），便于内网一键拉起。

---

## 技术模块详解（是什么 · 为何选型 · 解决什么问题）

以下为 OpenAgentic **已实现阶段**各技术模块的说明，便于面试展开与架构评审对齐。

### 1）FastAPI：应用工厂、生命周期与健康检查

**是什么、功能与用途**

- **FastAPI**：基于 Python 类型提示的 **ASGI Web 框架**，自动生成 **OpenAPI（Swagger）** 文档，原生支持 **异步** 路由与依赖注入。
- **应用工厂**：用函数（如 `create_app()`）创建 `FastAPI` 实例，便于按环境（开发 / 测试 / 生产）挂载不同中间件、路由或 Mock。
- **生命周期（lifespan）**：在应用启动时建立 **全局资源**（如数据库连接池），在关闭时 **优雅释放**，避免连接泄漏。
- **健康检查（如 `GET /health`）**：给 **负载均衡、K8s probe、运维脚本** 一个轻量端点，判断进程是否存活、依赖（如 DB）是否可达。

**为何选用（考量）**

- 私有化场景需要 **自托管 HTTP API**，FastAPI 在 **异步 I/O**、**自动文档**、**Pydantic 校验** 上与项目技术栈一致，学习曲线对熟悉 Python 的团队友好。
- 应用工厂 + lifespan 是 **12-factor** 与可测试性的常见写法，后续接 **多 Worker、灰度** 时不至于把初始化逻辑写死在模块 import 副作用里。

**能解决什么问题**

- **启动有序**：先连库再收流量，避免「服务已监听但一查库就炸」的竞态。
- **运维可观测**：探活与编排系统集成，快速从「502」里区分 **进程挂了** 还是 **下游 DB 挂了**。
- **团队协作**：Swagger 降低前后端 **契约沟通成本**。

### 2）PostgreSQL 16

**是什么、功能与用途**

- **PostgreSQL**：开源 **关系型数据库管理系统（RDBMS）**，用 **SQL** 管理数据；提供 **ACID 事务**、表 / 约束 / 外键、多种 **索引**（B-tree、GIN、GiST 等）、**JSONB**、**全文检索**、窗口函数、CTE 等企业常用能力。
- **在本项目中的用途**：作为 **主持久化引擎**，存放 **用户、会话、消息** 等业务表；后续其他特性（如审计字段、多租户组织表）仍在同一套库内演进。
- **PostgreSQL 16**：选用较新大版本，在 **查询优化器、监控与运维工具链** 上相对更成熟；客户若固定基线可再钉小版本号。

**为何选用（考量）**

- **私有化与合规**：内网部署时客户更关心 **数据落点、备份恢复、权限模型**；PostgreSQL 生态成熟，**DBA 与等保材料**里可解释性强。
- **与 Python 后端栈契合**：与 **SQLAlchemy 2.0 + Alembic + asyncpg** 组合为事实标准之一，降低长期维护的「冷门栈」风险。
- **可扩展而非换产品**：向量能力通过 **扩展（见下一节 pgvector）** 叠加，无需为 RAG 单独引入另一套数据库品牌，**采购与运维边界**更简单。

**能解决什么问题**

- **强一致业务数据**：会话与消息的写入、删除、查询在 **单库事务** 内完成，避免「对话在缓存里、落库失败用户不知道」类问题。
- **备份与容灾**：沿用成熟的 **pg_dump / 主从 / PITR** 等方案，满足企业 **RPO / RTO** 讨论框架。
- **复杂查询与演进**：权限、统计、运营报表等后续需求可用 **标准 SQL + 索引** 解决，不过早绑死专用存储。

### 3）pgvector 扩展

**是什么、功能与用途**

- **pgvector**：安装在 PostgreSQL 上的 **扩展（extension）**，提供 **`vector` 类型** 及 **距离 / 近邻查询** 能力（如欧氏、余弦、内积等语义，以扩展与版本文档为准），并支持 **向量索引**（如 **IVFFlat、HNSW** 等，视 PG 与扩展版本而定），用于对 **embedding 向量** 做 **相似度检索**。
- **在本项目中的用途**：与 README **Phase 4（知识库 / RAG）** 对齐 —— 将 **文档块向量** 与 **来源 metadata** 存在库内，与 **用户 / 会话 / 知识库** 等关系数据 **同实例关联**；当前阶段可为 schema **预留列或独立表**，逐步上线检索链路。
- **与「只用 PostgreSQL」的关系**：它 **不改变** PostgreSQL 作为关系库的本质，只是在同一进程内 **增加一种数据类型与算子**，由 `CREATE EXTENSION vector` 启用。

**为何选用（考量）**

- **与业务库同事务、同连接**：检索结果可与 **租户 / ACL / 文档版本** 等条件 **在同一条 SQL 或同一事务** 中过滤，减少「向量库与业务库数据不一致」的同步难题。
- **运维组件数少**：备份、监控、告警仍主要围绕 **PostgreSQL**；相对「专用向量数据库 + 业务库」双栈，**内网防火墙策略与成本说明** 更直观。
- **路线与产品一致**：产品规划明确 **pgvector 存嵌入**；先选定扩展路径，避免先做一套 Chroma / Milvus 再 **整体搬迁向量存储** 的重迁移。

**能解决什么问题**

- **RAG 近邻检索**：按 query embedding 取 **Top-K 文档块**，供 LLM **有依据生成**。
- **带约束的语义检索**：例如「仅在某用户可见的知识库集合内做向量检索」，用 **外键 + WHERE** 与向量排序组合完成。
- **证据链与版本**：向量与 **chunk_id、文件版本号** 同存，便于 **重建索引、回放评测** 时对齐「当时用的哪版材料」。

### 4）SQLAlchemy 2.0 异步 ORM 与 asyncpg

**是什么、功能与用途**

- **SQLAlchemy 2.0**：Python 生态主流的 **ORM / SQL 工具包**；2.x 风格统一了 **Core 与 ORM**，并一等支持 **异步（AsyncSession）**。
- **异步 ORM**：路由与数据库 I/O 使用 `async` / `await`，在等待数据库响应时 **不阻塞事件循环**，可并发处理更多请求。
- **asyncpg**：高性能 **异步 PostgreSQL 驱动**，常与 `postgresql+asyncpg` 连接串配合 SQLAlchemy 使用。

**为何选用（考量）**

- 项目同时存在 **REST 短请求** 与 **SSE 长连接**；异步栈避免「一个慢查询拖住整进程」的典型痛点。
- ORM 提供 **模型、关系、迁移（与 Alembic 协同）** 的可维护性，比手写裸 SQL 更适合持续迭代的业务表结构。

**能解决什么问题**

- **并发与延迟**：在高并发读多写场景下更好地利用单进程 **I/O 并行**。
- **可维护性**：表结构以 Model 与迁移文件为 **单一事实来源**，减少「环境之间 schema 不一致」。
- **类型与校验**：与 Pydantic 模型分层配合，**入库前校验** 更清晰。

### 5）Alembic 数据库迁移

**是什么、功能与用途**

- **Alembic**：SQLAlchemy 官方推荐的 **数据库 schema 版本管理工具**，通过「迁移脚本」描述 **增量 DDL**（建表、加列、索引、回滚）。

**为何选用（考量）**

- 企业项目从第一天就要假设 **多环境**（开发、测试、预发、生产）与 **多人协作**；没有迁移工具则只能靠手工执行 SQL，**不可重复、不可审计**。
- 与 SQLAlchemy Model **同源演进**：先改模型再生成 / 编写 revision，降低「代码与库结构漂移」。

**能解决什么问题**

- **可重复部署**：新环境 `alembic upgrade head` 即可对齐 schema。
- **可回滚**：出问题可 `downgrade` 有计划撤退（仍需谨慎与备份）。
- **变更审计**：每次迁移有版本号与提交记录，满足 **变更管理** 与排查需要。

### 6）Pydantic Settings 集中配置

**是什么、功能与用途**

- **Pydantic v2 Settings**：从 **环境变量、`.env` 文件** 等来源读取配置，并做 **类型转换与校验**（如 `DATABASE_URL` 必须是合法 URL、端口为 int）。
- **集中配置**：数据库 URL、JWT 密钥、LiteLLM 相关环境变量等在 **单一 `Settings` 对象** 注入，避免在代码各处 `os.getenv` 散落。

**为何选用（考量）**

- 与 FastAPI **依赖注入**天然契合：`get_settings()` 可作为依赖，便于单测时替换配置。
- **失败快**：启动时即发现缺 key、类型错误，而不是运行到一半才抛错。

**能解决什么问题**

- **环境一致性**：减少「我本地能跑、上 Docker 就挂」的配置类故障。
- **密钥管理**：明确哪些变量必填，便于对接 **K8s Secret / 客户密钥柜**。
- **文档化**：字段即文档，新成员上手快。

### 7）认证与会话：注册 / 登录、JWT（python-jose）、bcrypt；对话 CRUD

**是什么、功能与用途**

- **注册 / 登录**：用户身份入驻与凭证校验；密码经 **bcrypt** 等算法 **单向哈希** 存储，不存明文。
- **JWT（JSON Web Token）**：服务端签发 **自包含声明** 的令牌，客户端在后续请求中携带 **Authorization: Bearer**，用于 **无状态** 认证（可配合 refresh）。**python-jose** 用于编码 / 解码与校验签名。
- **对话 CRUD**：对「会话 thread」与「消息 messages」的创建、列表、删除等，支撑多会话产品与后续审计。

**为何选用（考量）**

- **私有化 SaaS / 内网门户** 常见模式是 JWT + REST，前后端分离清晰；无状态 API 便于 **水平扩展**（会话态不绑死单机内存）。
- bcrypt 为业界默认的密码哈希选择之一，抗彩虹表与暴力破解成本可预期。

**能解决什么问题**

- **多用户隔离**：没有认证则无法做 **按用户的数据隔离** 与配额。
- **对接企业 SSO 的演进空间**：当前 JWT 基线可逐步扩展为 **OIDC / LDAP** 等（视客户需求）。
- **安全基线**：避免弱密码存储与明文会话 token 满天飞。

### 8）LLM：LiteLLM 统一网关与 SSE 流式返回

**是什么、功能与用途**

- **LiteLLM**：面向多种大模型厂商的 **统一调用层**，将不同 SDK / 端点差异收敛为 **兼容 OpenAI 的接口形态**，并支持 **流式 chunk**、路由、密钥管理等能力（具体以官方版本为准）。
- **SSE（Server-Sent Events）**：基于 HTTP 的 **单向流式** 推送，浏览器用 `EventSource` 或 fetch 流读；适合 **逐 token / 逐段** 把模型输出推给前端。

**为何选用（考量）**

- **100+ Provider** 对接若自研适配层成本高、易碎；LiteLLM 把「换模型 = 改配置」产品化，符合平台型产品 **降低边际对接成本** 的目标。
- 对话类产品 **用户体感** 强依赖流式；SSE 在浏览器与代理上比纯 WebSocket 更易 **穿透部分企业网关**（仍视客户网络策略而定）。

**能解决什么问题**

- **厂商锁定缓解**：同一套后端接口可切换 **国内 / 国外 / 私有化** 模型供应商。
- **首字延迟（TTFB）**：流式输出让用户更快看到反馈，减少「卡死感」。
- **统一观测面**：便于在网关层做 **日志、限流、计费埋点**（与 Phase 5 路线衔接）。

### 9）前端：React + Vite + TailwindCSS + Zustand；与后端 REST + SSE

**是什么、功能与用途**

- **React**：组件化 UI 库（版本以 `ui/package.json` 为准）。
- **Vite**：现代前端 **构建与开发服务器**，冷启动快、HMR 体验好。
- **TailwindCSS**：**工具类优先** 的 CSS 框架，快速搭管理台与对话 UI，减少手写 CSS 碎片文件。
- **Zustand**：轻量 **客户端状态管理**，适合存 **当前用户、会话列表、流式消息缓冲区** 等，比 Redux 更薄。
- **REST + SSE**：认证与 CRUD 走 **JSON REST**；发送消息走 **SSE** 读流，前后端职责边界清楚。

**为何选用（考量）**

- 企业内网管理台类界面 **组件化 + 实用样式** 是主流路径；Vite 提升 **单人全栈** 开发效率。
- Zustand 足够支撑 **会话切换、流式追加** 而不引入过重样板代码。

**能解决什么问题**

- **开发效率**：快速迭代对话页、模型选择、错误提示等 UX。
- **与后端契约清晰**：REST 文档与类型（可配合 OpenAPI 生成 TS 类型）减少联调摩擦。
- **流式 UX**：SSE 消费侧可独立处理 **重连、中断、loading 态**。

### 10）交付：Docker Compose 拉起应用与数据库

**是什么、功能与用途**

- **Docker**：应用与其依赖以 **镜像** 交付，环境差异（库版本、系统库）被容器边界吸收。
- **Docker Compose**：用 **声明式 YAML** 定义多容器拓扑（如 `app` + `postgres`）、网络、卷、环境变量，一条命令 `docker compose up` 拉起整套。

**为何选用（考量）**

- 私有化客户现场往往是 **「给一台 Linux + 内网仓库」**；Compose 是最低摩擦的 **可重复演示与 PoC** 交付形态。
- PostgreSQL 与业务版本可 **钉死在 compose 文件**，减少「口头交接」导致的版本漂移。

**能解决什么问题**

- **一键复现**：销售 / 售前 / 客户运维用同一套文件起环境，缩短 **从 0 到可点通** 的时间。
- **隔离与回滚**：容器删了重建，配合 volume 策略控制 **数据是否持久化**。
- **为 K8s 演进铺路**：Compose 验证稳定后，可将镜像与配置 **迁移到 Helm / K8s**，而非从零发明部署故事。

---

## 规划能力总览（Phase 2–6）

与简历 / 路线图表述一致（**实现进度见文首表格**）：

- **Phase 2**：Agent CRUD、**ReAct** 执行器、工具注册表、**MCP 客户端**、执行历史。
- **Phase 3**：工作流引擎（JSON DAG、拓扑排序、异步并行、变量模板）。
- **Phase 4**：知识库 / RAG（上传、分块、嵌入、pgvector 检索、与 Agent / 工作流集成）。
- **Phase 5**：多租户、用量与计费、Prometheus、结构化日志、**correlation ID** 全链路等。
- **Phase 6**：工作流可视化（如 React Flow）、知识库管理、生产级 Compose（Nginx 等）。

---

## 技术栈总览

| 分层 | 技术选型 |
|------|----------|
| **运行时** | Python 3.12 |
| **Web 框架** | FastAPI |
| **ORM / DB 驱动** | SQLAlchemy 2.0 async + **asyncpg** |
| **数据库** | PostgreSQL 16 + **pgvector** |
| **配置** | Pydantic Settings |
| **迁移** | Alembic |
| **LLM 网关** | LiteLLM（多厂商统一入口、流式） |
| **认证** | JWT（python-jose）+ bcrypt |
| **前端** | React + Vite + TailwindCSS + Zustand |
| **容器** | Docker Compose |

---

## 架构设计

本节把 **请求路径总览**、**分层与组件**、**仓库目录** 合并在一处：先看数据怎么流，再对照代码落在哪个包。

### 逻辑架构简图

```
  ui/ — REST + SSE
         │
         ▼
  FastAPI — core/auth · core/chat · core/llm → LiteLLM
         │
         ▼
  PostgreSQL（pgvector 镜像已就绪；业务 RAG 见 Phase 4）
```

### 逻辑分层详解（与仓库 `src/openagentic/` 目录规划一致）

```
                    ┌─────────────────────────────────┐
                    │  React（浏览器 / 内网部署）      │
                    │  REST：认证、对话 CRUD           │
                    │  SSE：流式补全                   │
                    └───────────────┬─────────────────┘
                                    │ HTTPS（内网）
                                    ▼
┌───────────────────────────────────────────────────────────────────┐
│  FastAPI（openagentic.main）                                       │
│  ├── deps：DB Session、当前用户（JWT）                             │
│  ├── core/auth：注册、登录、refresh、me                            │
│  ├── core/chat：会话、消息持久化                                  │
│  └── core/llm：LiteLLM 封装 → 各厂商 API                          │
└───────────────────────────────┬───────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│  PostgreSQL 16                                                     │
│  ├── 业务表：用户、会话、消息等                                    │
│  └── pgvector：为后续 RAG / 记忆检索预留（路线图中 Phase 4）       │
└───────────────────────────────────────────────────────────────────┘
```

### 项目结构（代码布局）

```
src/
├── openagentic_entry/   # 控制台入口：引导 pip install -e 后再加载 CLI（见 pyproject [project.scripts]）
└── openagentic/
    ├── main.py              # 应用工厂、lifespan、structlog
    ├── config.py / deps.py
    ├── cli/                 # 终端 ReAct CLI（entry、repl、providers、tools、platform_adapter 等子模块）
    ├── core/
    │   ├── auth/            # Phase 1：注册登录 JWT
    │   ├── chat/            # Phase 1：会话消息 + SSE
    │   └── llm/             # Phase 1：LiteLLM
    ├── agent/               # Phase 2 已实现（基础版）
    ├── mcp/                 # Phase 2 已实现（基础版）
    ├── workflow/            # Phase 3 已实现
    ├── knowledge/           # Phase 4 占位
    ├── tenant/              # Phase 5 占位
    ├── observability/       # Phase 5 占位
    └── db/                  # session、Base
ui/                          # Phase 1 前端；Phase 6 部分能力持续迭代
extensions/android/          # 可选扩展（若有）
alembic/                     # 迁移脚本目录（revision 需维护）
```

**设计要点**

- **异步优先**：数据库与会话链路采用 async，避免阻塞事件循环，利于高并发下的 SSE 长连接场景扩展。
- **网关抽象**：LiteLLM 将「模型名、base_url、密钥、流式协议」差异收口到统一配置，产品侧只暴露「可选模型列表 + 流式对话 API」，降低对接新厂商的边际成本。
- **单体演进路径**：当前为 **模块化单体**（`agent/`、`workflow/`、`knowledge/`、`mcp/` 等包已占位），便于先跑通核心闭环，再按 Phase 填充，避免过早微服务化带来的运维负担。
- **CLI 平台适配层**：`openagentic.cli.platform_adapter` 统一封装 Windows / Unix 在事件循环策略、按键读取、清屏、文件权限等差异，业务交互层不再散落 `os.name` 分支。

---

## 核心模块与 API 边界

| 模块 | 职责 | 说明 |
|------|------|------|
| **config** | 环境区分、密钥、数据库 URL | Pydantic Settings，12-factor 友好 |
| **db** | Session、Base Model | 与 Alembic 协同演进 schema |
| **auth** | 注册登录、JWT、密码哈希 | 企业内网仍需最小权限与审计字段扩展位 |
| **chat** | 多会话、消息列表、发送消息 | SSE 将 token 流写回前端，需处理断开与超时 |
| **llm** | 调用 LiteLLM | 统一错误类型、重试策略、usage 记录（为后续计费埋点） |

**API 边界（与实现一致）**

- 认证：`POST /api/auth/register`、`/login`、`/refresh`，`GET /api/auth/me`
- 对话：`GET/POST /api/conversations`，`GET/POST /api/conversations/{id}/messages`（发送在 **`stream=true`** 时为 **SSE**）
- 运维：`GET /health`；模型：`GET /api/models`
- **`/api/agents`**、`/api/agents/{id}/execute`、`/api/agents/{id}/executions`、`/api/agent/message` 已在 Phase 2 提供最小可用实现；`/api/sessions`、`/api/channels` 与 `/api/presence` 仍保留兼容性 stub。

---

## 工程化与非功能需求

- **可部署性**：Docker Compose 定义 Postgres 与应用依赖，便于在客户内网复现相同拓扑；Postgres 服务建议配置 **healthcheck**，应用 **`depends_on` 条件** 等待数据库就绪。
- **可观测性（路线）**：Phase 5 明确 Prometheus、structlog、correlation ID —— 与 **Agent 可观测性** 学习主题对齐（跨请求 trace）。**当前仓库**：`structlog` 已在启动路径接入；其余按路线图迭代。
- **安全**：JWT + bcrypt 基线；后续多租户与 **操作审计** 需与会话、模型调用日志关联。
- **静态代码质量**：已接入 SonarCloud（见 `.github/workflows/sonarcloud.yml` 与 `sonar-project.properties`），PR 会基于测试覆盖率做质量分析。
- **质量与安全检查流水线**：新增 `.github/workflows/quality-security.yml`，覆盖 `ruff`、`mypy`、`bandit`、`pip-audit` 与 `schemathesis`（动态 API 检查）。

### SonarCloud 配置说明

1. 在 SonarCloud 创建项目并绑定本仓库。
2. 在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 中添加：
   - `SONAR_TOKEN`（必需）
3. 首次执行可在 Actions 页手动触发 `SonarCloud` 工作流。
4. 质量规则、质量门禁（Quality Gate）在 SonarCloud 项目后台配置。

### 本地执行质量检查

```bash
# 静态质量
ruff check src tests
mypy
bandit -r src/openagentic -c pyproject.toml

# 依赖漏洞
pip-audit

# 动态 API 检查（公共无鉴权端点）
APP_ENV=production PYTHONPATH=src uvicorn openagentic.main:app --host 127.0.0.1 --port 8000
curl -fsS http://127.0.0.1:8000/openapi.json -o openapi.json
python -c "import json; s=json.load(open('openapi.json')); keep={'/health','/api/models','/api/sessions','/api/channels','/api/presence'}; s['paths']={k:v for k,v in s.get('paths',{}).items() if k in keep}; json.dump(s, open('openapi.public.json','w'), ensure_ascii=False, indent=2)"
schemathesis run --url http://127.0.0.1:8000 --include-method GET --max-examples 20 ./openapi.public.json
```

---

## 难点与取舍

- **「企业级」与迭代速度**：先完成 **账号 + 多会话 + 流式 + 自建库**，再叠 Agent / MCP / RAG，避免一次性大而全导致无法交付可演示版本。
- **pgvector 与关系库同实例**：简化运维与事务边界；超大规模时再评估向量库拆分。
- **前端与后端解耦**：REST / SSE 契约清晰，便于未来替换管理端技术栈或增加移动端。

---

## 一次流式对话请求的完整生命周期

> 从用户点击发送到看到回复，后端完整链路如下：

```
用户点击「发送」
  → 前端 POST /api/conversations/{id}/messages  (body: { content: "你好", stream: true } 等，以 OpenAPI 为准)
  → Nginx / 反向代理转发（如有）
  → FastAPI 路由匹配
  → 依赖注入：get_current_user() 从 Authorization header 取 JWT → python-jose 验签 → 取 sub(user_id) → 查库确认用户存在
  → 依赖注入：get_db_session() 从连接池取 AsyncSession
  → Service 层：
    1. 验证 conversation_id 属于 current_user（防越权）
    2. 将用户消息写入 messages 表（role="user"）
    3. 从 messages 表拉该会话历史消息（按时间排序，可能截断到最近 N 条以控制 token）
    4. 构造 messages 列表：[system_prompt, ...history, user_message]
    5. 调用 LiteLLM acompletion(model="...", messages=..., stream=True)
  → LiteLLM 内部：
    - 根据 model 前缀路由到对应 Provider
    - 拼接 base_url + api_key（从环境变量 / Settings）
    - 发起 HTTPS 请求到模型厂商 API
  → 模型厂商返回流（SSE / chunk）
  → 后端 StreamingResponse：
    async for chunk in llm_stream:
      text_delta = chunk.choices[0].delta.content  # 以实际 chunk 结构为准，需防御性解析
      yield f"data: {json.dumps({'content': text_delta})}\n\n"
    # 流结束后
    将完整 assistant 回复写入 messages 表（role="assistant"）
    记录 token usage（input_tokens, output_tokens）到日志或表
    yield f"data: [DONE]\n\n"   # 或项目约定的事件形态
  → 前端 fetch ReadableStream 消费：
    逐 chunk 追加到消息气泡，实现打字机效果
    收到结束事件后标记消息完成
```

**关键细节**

- **断连处理**：如果用户在流式过程中关闭页面，FastAPI 会抛 `asyncio.CancelledError`，需要在 try / finally 中 **取消上游请求**（避免白耗 token）并 **将已生成的部分内容存库**。
- **错误处理**：模型 API 返回 429（限流）时，LiteLLM 可配置 **自动重试 + 指数退避**；返回 500 时降级到备用模型或返回友好错误。
- **Token 截断**：如果历史消息太长超过模型 context window，需要在构造 messages 时 **从最早的消息开始丢弃**，保留 system prompt + 最近的对话。

---

## 开发路线 Phase 0–6（Todo）

### Phase 0：脚手架 + Docker（已完成）

- [x] FastAPI 应用工厂 + 生命周期（含 `structlog` 启动日志）
- [x] PostgreSQL（`pgvector/pgvector:pg16`）+ Docker Compose + healthcheck
- [x] SQLAlchemy 2.0 async ORM + Alembic 工程
- [x] Pydantic Settings、健康检查、Compose 基础拓扑

### Phase 1：认证 + 聊天 + LLM 流式（已完成）

- [x] 注册 / 登录 / JWT
- [x] 会话与消息 CRUD
- [x] LiteLLM 对接 + SSE 流式返回
- [x] `ui/` 与 Phase 1 API 协同

### Phase 2：Agent 系统 + MCP（基础版已完成）

- [x] Agent CRUD
- [x] 最小 ReAct 执行器
- [x] 工具注册表
- [x] MCP Client（HTTP JSON-RPC）
- [x] 执行历史落库与查询

### Phase 3：工作流引擎（已完成）

- [x] Workflow CRUD、运行触发、运行查询、运行取消
- [x] JSON DAG 校验 + 拓扑执行
- [x] 模板变量传参（`{{input.*}}` / `{{nodes.*}}`）
- [x] 节点级重试 / 超时 + 结构化 trace
- [x] 对应测试覆盖（API、边界行为、配置持久化）

### Phase 4：知识库 / RAG（部分完成）

- [x] 知识库数据库模型与迁移 (`add_knowledge_tables.py`)
- [x] 文档上传与管理 API
- [x] 文档分块与向量存储
- [x] 向量检索 API
- [x] 与 Agent 集成 (`knowledge_search` 工具)
- [ ] 批量文档处理
- [ ] 向量索引优化
- [ ] 多模态文档支持
- [ ] 检索结果重排序

### Phase 5：多租户 + 计费 + 可观测性（未完成）

- [ ] 多租户与组织隔离
- [ ] 用量统计 / 计费 / 配额
- [ ] Prometheus 指标与告警
- [ ] correlation ID 全链路追踪

### Phase 6：前端增强与 Skills 生态系统（进行中）

#### 前端页面（已完成）
- [x] `ui/` 多页面框架
- [x] Sessions 页面
- [x] Settings 页面
- [x] **Skills 页面**（前端 UI 与静态数据）
- [x] Channels 页面
- [x] Devices 页面

#### Skills 支持计划（Todo List）

##### 短期目标（Phase 6.1 - Skills 基础）
- [ ] **Skills 数据库模型**：创建 skills 数据表，支持技能元数据存储
- [ ] **Skills CRUD API**：实现技能的创建、读取、更新、删除接口
- [ ] **技能状态持久化**：保存用户技能启用/禁用状态到数据库
- [ ] **前端-后端集成**：连接 Skills 页面到后端 API
- [ ] **技能分类与搜索**：实现技能分类、标签、搜索功能

##### 中期目标（Phase 6.2 - Skills 管理）
- [ ] **技能安装系统**：支持从技能市场安装技能
- [ ] **技能版本控制**：支持技能版本管理和升级
- [ ] **技能依赖管理**：处理技能间的依赖关系
- [ ] **技能权限控制**：基于用户角色的技能访问控制
- [ ] **技能执行统计**：记录技能使用情况和性能指标

##### 长期目标（Phase 6.3 - Skills 生态系统）
- [ ] **技能市场（ClawHub）**：社区技能分享平台
- [ ] **技能开发工具包**：提供技能开发模板和SDK
- [ ] **技能自动化测试**：技能质量验证和测试框架
- [ ] **技能安全沙箱**：技能执行环境隔离
- [ ] **技能计费系统**：付费技能的支持

#### 其他前端增强
- [ ] 工作流可视化编辑器（React Flow）
- [ ] 知识库管理 UI
- [ ] Agent 模板市场
- [ ] 生产级 Nginx + Compose 拓扑闭环
- [ ] 响应式设计与移动端适配
- [ ] 多语言国际化支持
- [ ] 主题切换与自定义样式

---

#### 当前 Skills 实现状态
- **前端 UI**：✅ 已完成（SkillsPage.tsx）
- **技能数据模型**：✅ TypeScript 接口已定义
- **预置技能**：✅ 7个内置技能 + 3个社区技能
- **UI 功能**：✅ 技能启用/禁用、分类筛选、搜索
- **后端支持**：⚠️ 部分实现（Tool 系统基础）
- **数据库存储**：❌ 未实现
- **API 接口**：❌ 未实现
- **技能市场**：❌ 未实现

#### 技术架构说明
项目采用 **Tools → Skills** 演进路径：
1. **Phase 2 (当前)**：基础 Tool 系统（`agent/tools.py`）
   - ToolRegistry 工具注册表
   - 内置工具：echo、current_time、calculator、knowledge_search
   - Agent 级别的工具配置

2. **Phase 6 (进行中)**：完整 Skills 系统
   - 技能市场和管理
   - 技能安装和版本控制  
   - 技能依赖和权限管理
   - 社区技能分享（ClawHub）

---



## Skills 支持现状与路线图

### 当前实现
OpenAgentic 已建立完整的 Skills 前端界面和基础架构，为技能生态系统打下坚实基础：

#### ✅ 已完成的组件
1. **前端 Skills 页面** (`ui/src/pages/SkillsPage.tsx`)
   - 完整的技能管理界面
   - 技能分类、筛选、搜索功能
   - 技能启用/禁用控制
   - 美观的卡片式布局

2. **技能数据模型**
   ```typescript
   interface Skill {
     id: string        // 技能唯一标识
     name: string      // 技能名称
     description: string  // 技能描述
     version: string   // 版本号
     author?: string   // 作者
     category: string  // 分类
     tags: string[]    // 标签
     enabled: boolean  // 是否启用
     source: 'bundled' | 'managed' | 'workspace' | 'clawhub'  // 来源
   }
   ```

3. **预置技能库**
   - **内置技能**（7个）：文件操作、网页搜索、图像生成、代码分析、数据处理、自动化任务、安全执行
   - **社区技能**（3个）：网页抓取、PDF工具、OCR文字识别

4. **后端基础架构**
   - ToolRegistry 工具注册系统
   - Agent 工具配置支持
   - 知识库搜索工具集成

#### ⚠️ 待完善的组件
1. **后端 API**：缺少专门的 Skills CRUD 接口
2. **数据持久化**：技能状态未保存到数据库
3. **技能安装**：无法从市场安装新技能
4. **版本管理**：缺少技能版本控制
5. **权限控制**：未实现基于角色的技能访问

### 技术架构
```
Frontend (React)
    ↓
Skills Page UI (静态数据)
    ↓
[待连接] ← Skills API (待实现)
    ↓
Skills Service (待实现)
    ↓
Database (PostgreSQL + Skills 表)
    ↓
Tool Registry (已实现)
    ↓
Agent Execution
```

### 开发优先级建议
1. **高优先级**：Skills 数据库模型和基础 API
2. **中优先级**：前端-后端集成和状态持久化  
3. **低优先级**：技能市场和高级功能

### 扩展建议
1. **技能开发 SDK**：提供技能开发模板和工具
2. **技能商店**：建立技能分发和盈利模式
3. **技能组合**：支持技能组合和编排
4. **技能分析**：使用统计和性能监控

---
## 快速启动

```bash
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic

# 建议 Python 3.12 + venv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 必须在仓库根目录执行一次可编辑安装，否则 `openagentic` / `import openagentic` 会报找不到模块
pip install -e ".[dev]"     # 以 pyproject / README 仓库说明为准

cp .env.example .env
# 填写 DATABASE_URL、JWT 密钥、各厂商 API Key / LiteLLM 所需变量

docker compose up -d postgres
# 待 Alembic revision 齐全后：alembic upgrade head
# 开发环境（且 APP_ENV=development）：可能由 create_all 建表，见上文

PYTHONPATH=src uvicorn openagentic.main:app --host 0.0.0.0 --port 8000
```

- **Swagger / OpenAPI**：`http://<host>:8000/docs`
- **健康检查**：`http://<host>:8000/health`
- **前端**：进入 `ui/` 按 `package.json` 脚本启动（如 `npm install && npm run dev`），API 基地址指向后端。

**Windows 补充**

- 拉代码或切换分支后，若改了依赖或入口，请在仓库根目录再次执行：`pip install -e .`（或 `pip install -e ".[dev]"`）。
- 控制台命令 `openagentic` 由 `openagentic_entry` 包引导：若尚未安装可编辑包，首次运行会尝试自动执行 `pip install -e <仓库根>`；仍失败时请手动执行上一行的 `pip`。
- 在 Windows 上，CLI **不会**在进程内自动反复执行 `pip install -e .`（避免替换正在使用的启动器脚本导致失败或 WinError 32）；源码有更新时请自行重装可编辑包，或直接使用 `python -m openagentic.cli`。

---

## CLI 模式（直接对话）

无需启动 Web 服务，直接在终端与模型对话（支持本地 Ollama 或 OpenAI 兼容网关）：

```bash
cd /opt/open-agentic && source .venv/bin/activate

# 默认使用 qwen3:14b
python -m openagentic.cli

# 使用 OpenAI 兼容网关（如 DeepSeek）
python -m openagentic.cli --provider openai -m deepseek-chat

# 指定模型
python -m openagentic.cli -m ollama/deepseek-r1:32b

# 带系统提示
python -m openagentic.cli -s "你是一个Python专家，用中文回答"

# 也可以用注册的命令（需已 pip install -e .）
openagentic
```

`pyproject.toml` 中 `openagentic` 入口指向 **`openagentic_entry:main`**：先保证包可导入，再调用 `openagentic.cli`。若出现 `ModuleNotFoundError: No module named 'openagentic'` 或 `'openagentic_entry'`，一律在仓库根目录执行 `pip install -e .` 后重试。

CLI Provider 说明：

- `--provider auto`（默认）：按模型前缀或默认配置自动选择 provider。
- `--provider <id>`：可指定 `openai`、`anthropic`、`xai`、`gemini`、`deepseek`、`qwen`、`ollama` 等。
- CLI 内可用 `/providers` 查看厂商列表，`/provider <id>` 切换并进入该厂商配置向导，`/provider-config [id]` 单独编辑配置。
- 未配置必需的 API Key 时，CLI 会在进入会话前强制进入配置向导，配置完成后才允许继续使用。
- 模型始终由显式配置决定（`-m`、`/model`、`default_model`、`OPENAI_CHAT_MODEL`）；API Key 仅用于鉴权，不负责“指定模型”。
- Provider 配置文件默认位于 `.openagentic/model_providers.json`（可通过 `MODEL_PROVIDER_CONFIG_PATH` 调整）。

CLI 内置命令：

| 命令 | 说明 |
|------|------|
| `/clear` | 清除对话历史 |
| `/model ollama/qwen3:4b` | 切换模型 |
| `/system <prompt>` | 设置系统提示 |
| `/quit` | 退出 |

DeepSeek（OpenAI 兼容）示例：

| 场景 | 建议模型 |
|------|------|
| 默认对话（V3.2 非思考） | `deepseek/deepseek-chat` |
| 推理优先（V3.2 思考模式） | `deepseek/deepseek-reasoner` |

说明：当前内置 DeepSeek profile 的模型顺序为 `deepseek-reasoner` 优先于 `deepseek-chat`。

可用模型（Ollama 本地）：

| 模型 | 说明 |
|------|------|
| `ollama/qwen3:14b` | Qwen3 14B（默认，带思考） |
| `ollama/qwen3:14b-nothink` | Qwen3 14B（无思考，更快） |
| `ollama/qwen3:4b` | Qwen3 4B（轻量，带思考） |
| `ollama/qwen3:4b-nothink` | Qwen3 4B（轻量，无思考） |
| `ollama/deepseek-r1:32b` | DeepSeek R1 32B |

---

## API 端点

### 认证

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `GET /api/auth/me`

### 对话

- `GET/POST /api/conversations`
- `GET/DELETE /api/conversations/{id}`
- `GET/POST /api/conversations/{id}/messages`（**流式**：查询参数或 body 中带 `stream=true` 等，以 `/docs` 为准）

### 其他

- `GET /health`
- `GET /api/models`
- `GET /api/llm/providers`、`PUT /api/llm/providers/{provider_id}`、`PUT /api/llm/default-model`
- `GET/POST /api/agents`、`GET/PATCH/DELETE /api/agents/{agent_id}`、`POST /api/agents/{agent_id}/execute`
- `GET /api/agents/{agent_id}/executions`、`POST /api/agent/message`
- `GET /api/sessions`、`GET /api/channels`、`GET /api/presence` 仍为简化桩响应（兼容旧前端）。

---

## 前端 `ui/`

- 技术栈：**React + Vite + TailwindCSS + Zustand**（版本以仓库为准）。
- **与后端协作**：REST 完成认证与会话 CRUD；发送消息通过 **SSE** 消费流式增量。
- **当前页面能力（示例）**：Sessions、Settings、Skills、Channels、Devices 等 —— 以 `ui/src` 路由与页面为准；**工作流可视化、知识库运营后台** 等属于路线图 Phase 6 / Phase 4 联动能力，**未承诺已全部可用**。

---

## 常见问题与排错

1. **数据库连不上**：检查 `DATABASE_URL` 是否与 Compose 端口、库名、用户密码一致；确认 Postgres 容器 **healthy** 后再启动 app。
2. **表不存在**：若尚无 Alembic `upgrade`，在 **开发环境** 确认 `APP_ENV=development` 与 `create_all` 行为；**生产禁止**依赖 `create_all`。
3. **SSE 被代理缓冲**：Nginx 需关闭响应缓冲（如 `proxy_buffering off`）、合理 `proxy_read_timeout`，否则打字机效果延迟。
4. **模型 401 / 429**：核对环境变量中的 Key 与 LiteLLM 路由；限流时加重试或降级模型。
5. **流中断后 DB 只有半条**：检查取消路径是否在 finally 中 **落库 partial** 并 **取消上游**。
6. **`openagentic` 报 `ModuleNotFoundError: No module named 'openagentic'`（或 `openagentic_entry`）**：未在仓库根目录执行可编辑安装。先 `cd` 到克隆下来的仓库根目录，激活 venv，执行 `pip install -e .`，再运行 `openagentic` 或 `python -m openagentic.cli`。
7. **pip 反复提示 `Ignoring invalid distribution ~...`（如 `~penagentic`）**：多为上次安装中断留下的损坏目录。关闭所有使用该 venv 的进程后，在 `.venv\Lib\site-packages`（或对应 venv 的 `site-packages`）中删除名称以 `~` 开头、且明显与 `openagentic` 相关的文件夹，再执行 `pip install -e .`。

---

## 仓库与贡献

- **GitHub**：[openagentic-ai/open-agentic](https://github.com/openagentic-ai/open-agentic)
- 欢迎 Issue / PR；大功能建议先对照 **Phase 路线图** 开讨论，避免与占位包设计冲突。

---

## 许可证

MIT
