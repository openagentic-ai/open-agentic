# OpenAgentic

企业级 AI Agent 平台 — Python (FastAPI) 后端

## 技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy 2.0 async + asyncpg
- **数据库**: PostgreSQL 16 + pgvector（关系 + 向量存储一体化）
- **LLM 网关**: LiteLLM（支持 100+ 大模型 Provider）
- **认证**: JWT (python-jose) + bcrypt 密码哈希
- **前端**: React 19 + Vite + TailwindCSS + Zustand
- **基础设施**: Docker Compose

## 快速启动

```bash
# 在服务器上（192.168.0.15）
cd /opt/openagentic
source .venv/bin/activate

# 启动 PostgreSQL
docker compose up -d postgres

# 运行应用
PYTHONPATH=src DATABASE_URL=postgresql+asyncpg://openagentic:openagentic@localhost:5433/openagentic \
uvicorn openagentic.main:app --host 0.0.0.0 --port 8000

# 访问 Swagger UI: http://192.168.0.15:8000/docs
```

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
- `POST /api/conversations/{id}/messages` - 发送消息（SSE 流式返回）

### 其他
- `GET /health` - 健康检查
- `GET /api/models` - 可用模型列表
- `GET /api/agents` - Agent 列表（待实现）
- `GET /api/sessions` - 会话列表（待实现）

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
├── workflow/             # DAG 工作流引擎（Phase 3）
├── knowledge/            # RAG 管线（Phase 4）
├── mcp/                  # Model Context Protocol（Phase 2）
├── tenant/               # 多租户（Phase 5）
├── observability/        # 指标 + 日志（Phase 5）
└── db/                   # 数据库 session + 基础模型
```

## 许可证

MIT
