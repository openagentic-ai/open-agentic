# OpenAgentic

企业级 AI Agent 平台 — Python (FastAPI) 后端 + React 前端。

**定位**：面向 **私有化 / 内网** 部署，将大模型对话以 **长期在线服务** 形态落在自有基础设施；会话与业务数据进 **自建 PostgreSQL**，模型调用通过 **LiteLLM** 统一对接多家厂商。多 Agent、工具编排、RAG、工作流等按 **Phase 路线图** 迭代。

**官网**：[openagentic-ai.github.io](https://openagentic-ai.github.io)

---

## 技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy 2.0 async + asyncpg
- **数据库**: PostgreSQL 16 + pgvector（关系数据与向量字段一体化，RAG 见 Phase 4）
- **LLM 网关**: LiteLLM（支持 100+ 大模型 Provider）
- **认证**: JWT (python-jose) + bcrypt 密码哈希
- **前端**: React 19 + Vite + TailwindCSS + Zustand（`ui/`）
- **基础设施**: Docker Compose；可选 `docker-compose.dev.yml` 本地开发

---

## 已落地能力（Phase 0–1）与实现要点

| 能力 | 实现方式（摘要） |
|------|------------------|
| **统一账号** | `POST /api/auth/register` 注册（bcrypt 存哈希）；`POST /api/auth/login` 签发 JWT；`POST /api/auth/refresh`；`GET /api/auth/me` 依赖注入解析 `Authorization: Bearer`。 |
| **多会话** | `Conversation` / `Message` REST：`GET/POST /api/conversations`，`GET/DELETE …/{id}`，`GET/POST …/{id}/messages`；**AsyncSession** 写入 PostgreSQL，`user_id` 外键隔离数据。 |
| **多厂商模型** | **`core/llm`** 封装 **LiteLLM**；`GET /api/models` 暴露可选模型；密钥与 `base_url` 经 **Pydantic Settings** 从环境变量注入。 |
| **流式对话** | `POST …/messages` 使用 **SSE**（`StreamingResponse` + 异步 chunk），降低首字延迟；鉴权在建立流前完成，断开时建议取消上游生成。 |
| **数据与迁移** | **`postgresql+asyncpg`** 连接池在 **lifespan** 中创建；**Alembic** 管理 schema；**pgvector** 扩展为 Phase 4 向量检索预留。 |
| **交付** | `docker compose up -d postgres` 拉起数据库；应用以 `uvicorn` 或 Compose 中 app 服务运行（见仓库 `docker-compose.yml`）。 |

**工程预留（与 Phase 5 对齐）**：会话/消息表可扩展 **token_usage、model_name**；中间件可挂 **request_id / correlation ID**；日志与 Prometheus 见路线图。

---

## 技术选型说明（简版）

- **FastAPI + 异步 ORM**：REST 与 **SSE 长连接** 并存时，避免同步阻塞事件循环；OpenAPI `/docs` 便于前后端契约对齐。  
- **PostgreSQL + pgvector**：业务强一致与 **RAG 向量** 同库演进，减少双栈同步；备份与权限模型对客户更可解释。  
- **LiteLLM**：把多厂商差异收口为 **配置 + 统一调用形态**，降低对接与切换成本。  
- **Docker Compose**：内网 PoC 与验收 **一键复现** PostgreSQL 版本与卷策略。

---

## 快速启动

```bash
# 示例：服务器上项目目录（以你实际路径为准，常见为 /opt/open-agentic 或 /opt/openagentic）
cd /opt/open-agentic
source .venv/bin/activate

# 启动 PostgreSQL
docker compose up -d postgres

# 运行应用（DATABASE_URL 按 .env 或环境修改）
PYTHONPATH=src DATABASE_URL=postgresql+asyncpg://openagentic:openagentic@localhost:5433/openagentic \
uvicorn openagentic.main:app --host 0.0.0.0 --port 8000

# Swagger UI: http://<服务器IP>:8000/docs
```

复制环境变量模板：`cp .env.example .env` 后按需填写 **数据库 URL、JWT 密钥、LiteLLM 相关变量**。

---

## API 端点

### 认证

- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录（返回 JWT）
- `POST /api/auth/refresh` - 刷新令牌
- `GET /api/auth/me` - 当前用户信息

### 对话

- `GET /api/conversations` - 对话列表
- `POST /api/conversations` - 创建对话
- `GET /api/conversations/{id}` - 获取对话详情
- `DELETE /api/conversations/{id}` - 删除对话
- `GET /api/conversations/{id}/messages` - 获取消息列表
- `POST /api/conversations/{id}/messages` - 发送消息（**SSE 流式**返回）

### 其他

- `GET /health` - 健康检查（负载均衡 / K8s probe）
- `GET /api/models` - 可用模型列表
- `GET /api/agents` - Agent 列表（**待实现**，见 Phase 2）
- `GET /api/sessions` - 会话列表（**待实现**）

---

## 开发路线

### Phase 0：脚手架 + Docker -- 已完成 ✅

- [x] FastAPI 应用工厂 + 生命周期管理
- [x] PostgreSQL + pgvector（Docker Compose）
- [x] SQLAlchemy 2.0 async ORM + Alembic 数据迁移
- [x] Pydantic Settings 配置管理
- [x] 健康检查端点
- [x] Docker Compose（app + postgres）

### Phase 1：认证 + 聊天 + LLM 流式 -- 已完成 ✅

- [x] 用户注册 + 登录（JWT + bcrypt）
- [x] 对话 CRUD
- [x] LLM 集成（LiteLLM 100+ 厂商）
- [x] SSE 流式聊天响应
- [x] 前端兼容 API 存根

### Phase 2：Agent 系统 + MCP

- [ ] Agent CRUD（创建、配置、删除）
- [ ] ReAct 执行器（工具调用循环）
- [ ] 内置工具：web_search、code_interpreter、http_request
- [ ] 工具注册表（Pydantic schema 定义）
- [ ] MCP（Model Context Protocol）客户端
- [ ] Agent 执行历史

### Phase 3：工作流引擎

- [ ] 工作流定义（JSON DAG：节点 + 边）
- [ ] DAG 引擎：拓扑排序 + 异步并行执行
- [ ] 节点类型：Start、End、LLM、Agent、Condition、Code、HTTP、Knowledge
- [ ] 变量传递，模板语法（`{{node_1.output}}`）
- [ ] 工作流执行记录 + 节点级状态
- [ ] 实时执行进度（WebSocket）

### Phase 4：知识库 / RAG

- [ ] 文档上传（PDF、DOCX、TXT、Markdown）
- [ ] 文本分块（递归字符分割）
- [ ] 向量嵌入（LiteLLM embedding）
- [ ] 向量存储（pgvector）
- [ ] 相似度检索
- [ ] 与 Agent、工作流集成

### Phase 5：多租户 + 计费 + 可观测性

- [ ] 租户（组织）管理
- [ ] 按租户用量追踪（Token 数、费用）
- [ ] Token/费用配额限制
- [ ] Prometheus 指标端点
- [ ] 结构化日志（structlog）
- [ ] 请求追踪（correlation ID）

### Phase 6：前端增强

- [ ] 工作流可视化编辑器（React Flow）
- [ ] 知识库管理界面
- [ ] Agent 模板市场
- [ ] 生产级 Docker Compose（Nginx + 持久卷）

---

## 项目结构

```
src/openagentic/
├── main.py              # FastAPI 应用工厂
├── config.py            # Pydantic Settings 配置
├── deps.py              # FastAPI 依赖注入（认证、数据库）
├── core/
│   ├── auth/            # JWT 认证 + 用户管理
│   ├── chat/            # 对话 + 消息
│   └── llm/             # LiteLLM 封装
├── agent/               # Agent 系统（Phase 2）
├── workflow/            # DAG 工作流引擎（Phase 3）
├── knowledge/           # RAG 管线（Phase 4）
├── mcp/                 # Model Context Protocol（Phase 2）
├── tenant/              # 多租户（Phase 5）
├── observability/       # 指标 + 日志（Phase 5）
└── db/                  # 数据库 session + 基础模型
```

---

## 逻辑架构（简图）

```
  React (ui/) — REST 认证 / 对话 CRUD + SSE 收流
                    │
                    ▼
  FastAPI (openagentic.main) — deps: JWT + AsyncSession
       ├── core/auth
       ├── core/chat
       └── core/llm → LiteLLM → 各厂商 API
                    │
                    ▼
  PostgreSQL 16 + pgvector — 用户 / 会话 / 消息（+ 未来向量与审计）
```

---

## 仓库与扩展

- **GitHub**：[openagentic-ai/open-agentic](https://github.com/openagentic-ai/open-agentic)  
- 仓库内另有 **`extensions/android`** 等扩展目录，详见各子目录说明。

---

## 许可证

MIT
