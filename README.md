# OpenAgentic

**企业私有化 AI 员工部署平台** — 给你的企业招一个永不离职的 AI 员工

[English](#english) | [中文](#核心理念)

---

## 核心理念

**别人的 AI 是工具，我们的 AI 是你的员工。**

OpenAgentic 为中小企业提供交钥匙式的 AI 私有化部署服务。我们帮你训练一个懂你业务的 AI 员工，部署在你自己的服务器上，数据从头到尾不出你的内网。

- 不请假、不离职、7×24 小时在岗
- 懂你的产品、价格、流程，说你们公司的话
- 数据私有化，不上传任何第三方平台
- 开源可审计，MIT 协议

## 架构

```
用户端（网页 · 微信 · 钉钉 · API）
    ↕  HTTPS / WebSocket
OpenAgentic 引擎（Rust 高性能网关 · Agent 调度 · 记忆系统）
    ↕
大模型层（本地部署 Ollama/vLLM 或 API 调用，100+ 模型可选）
```

## 核心能力

| 能力 | 说明 |
|------|------|
| **100+ 大模型** | LiteLLM 统一网关：OpenAI、Anthropic、Gemini、DeepSeek、通义千问、Ollama 等 |
| **多 Agent 协作** | 任务自动分解，多个专业 Agent 协同工作（客服、跟单、翻译、培训） |
| **三层记忆** | 工作记忆 → 短期记忆（压缩摘要）→ 长期记忆（向量存储） |
| **行业微调** | 基于你的业务数据微调模型，AI 员工越干越熟练 |
| **多渠道接入** | 网页、微信、钉钉、飞书、Telegram、Discord 等 15+ 消息通道 |
| **安全优先** | JWT + Argon2 认证、输入过滤、输出脱敏、审计日志、速率限制 |
| **工具生态** | 浏览器自动化、定时任务、Webhook、MCP 集成 |

## AI 员工能胜任什么岗位

- **跨境电商客服专员** — 精通多国语言，7×24 在线，产品参数/物流/退换货张口就来
- **外贸业务跟单员** — 自动识别买家意图，匹配报价方案，生成专业英文回复
- **门店前台接待员** — 餐饮/酒店/诊所的 AI 前台，营业时间/预约/价格自动应答
- **内部培训讲师** — 公司文档/SOP/制度全部学会，新员工有问必答

## 快速开始

```bash
# 克隆并构建
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic
cargo build --release

# 启动网关
./target/release/open-agentic gateway

# 健康检查
curl http://localhost:18789/health
```

### 配置认证

```bash
# 生成密码哈希
./target/release/open-agentic hash-password YOUR_PASSWORD

# 编辑 ~/.openclaw-rust/config.json
# 填入 jwt_secret、admin_username、admin_password_hash
# 详见下方配置示例

# 登录获取 token
curl -X POST http://localhost:18789/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "YOUR_PASSWORD"}'
```

## API 接口

| 接口 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/health` | GET | 公开 | 健康检查 |
| `/api/auth/login` | POST | 公开 | 登录获取 JWT |
| `/chat` | POST | 需要 | 对话（JSON） |
| `/chat/stream` | GET | 需要 | 流式对话（SSE） |
| `/models` | GET | 需要 | 可用模型列表 |
| `/voice/tts` | POST | 需要 | 文字转语音 |
| `/voice/stt` | POST | 需要 | 语音转文字 |
| `/api/agents` | GET/POST | 需要 | Agent 管理 |
| `/api/sessions` | GET/POST | 需要 | 会话管理 |
| `/ws` | WebSocket | 公开 | 实时通信 |

## 配置示例

配置文件：`~/.openclaw-rust/config.json`

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 18789
  },
  "ai": {
    "default_provider": "ollama",
    "providers": [
      {
        "name": "ollama",
        "base_url": "http://localhost:11434",
        "default_model": "qwen3:14b"
      }
    ]
  },
  "security": {
    "jwt_secret": "your-secret-key",
    "jwt_expiration_secs": 86400,
    "admin_username": "admin",
    "admin_password_hash": "$argon2id$...",
    "cors_origins": ["*"],
    "login_rate_limit": 5,
    "api_rate_limit": 10
  }
}
```

## 项目结构

```
open-agentic/
├── crates/                         # Rust 后端（17 个模块化 Crate）
│   ├── openagentic-core            # 核心类型、配置、错误处理
│   ├── openagentic-ai              # LiteLLM 统一 Provider（100+ 大模型）
│   ├── openagentic-agent           # 多 Agent 系统 + 技能进化
│   ├── openagentic-server          # HTTP/WS 网关 + JWT + 速率限制
│   ├── openagentic-memory          # 三层记忆系统
│   ├── openagentic-vector          # 向量存储（Qdrant/LanceDB/Milvus）
│   ├── openagentic-channels        # 消息通道集成
│   ├── openagentic-voice           # STT/TTS 语音服务
│   ├── openagentic-canvas          # 实时协作画布
│   ├── openagentic-browser         # 浏览器自动化
│   ├── openagentic-sandbox         # Docker/WASM 沙箱
│   ├── openagentic-tools           # 定时任务/Webhook/MCP
│   ├── openagentic-device          # 设备控制
│   ├── openagentic-security        # 输入过滤、输出校验、审计
│   ├── openagentic-acp             # Agent 能力协议
│   ├── openagentic-ws              # WebSocket 模块
│   └── openagentic-cli             # CLI 入口
├── ui/                             # Web UI（React 19 + Vite + TailwindCSS）
├── extensions/                     # 扩展功能
│   └── android/                    # Android App（实验性）
└── skills/                         # 技能定义
```

## 开发路线

- [x] Rust 后端网关编译运行
- [x] LiteLLM 统一 Provider（支持 100+ 大模型）
- [x] JWT 认证 + Argon2 密码哈希
- [x] 安全加固（CORS 白名单、速率限制、安全响应头）
- [ ] 对接 Ollama 测试对话
- [ ] Web UI 对接后端
- [ ] 行业微调模型集成
- [ ] Docker 容器化一键部署
- [ ] 多渠道消息接入（微信/钉钉）
- [ ] 种子客户落地验证

## 安全体系

- **认证**：JWT + Argon2 密码哈希
- **输入防护**：Prompt 注入检测（正则 + 关键词黑名单，多语言）
- **输出校验**：自动脱敏（API Key、密码、银行卡号）
- **速率限制**：按 IP 限制登录频率，按 Token 限制 API 调用
- **CORS**：可配置的来源白名单
- **安全头**：X-Content-Type-Options、X-Frame-Options、X-XSS-Protection、Referrer-Policy
- **沙箱**：Docker 和 WASM 隔离执行工具调用

## 系统要求

- **Rust**: 1.93+
- **Docker**: 可选（沙箱和容器化部署）
- **Chrome/Chromium**: 可选（浏览器自动化）

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。

---

## English

**OpenAgentic** — Enterprise Private AI Employee Deployment Platform

An open-source platform that deploys AI "employees" inside your company's own infrastructure. Your data never leaves your network.

### Key Features

- **100+ LLM Support** — Unified LiteLLM gateway: OpenAI, Anthropic, Gemini, DeepSeek, Qwen, Ollama, and more
- **Multi-Agent System** — Task decomposition across specialized agents
- **Industry Fine-tuning** — Train AI on your business data for domain-specific expertise
- **Private Deployment** — Docker containerized, runs on your own servers
- **Multi-Channel** — 15+ messaging integrations (Telegram, Discord, DingTalk, WeCom, Feishu)
- **Security First** — JWT + Argon2 auth, input filtering, output validation, audit logging, rate limiting
- **Open Source** — MIT License, fully auditable

### Quick Start

```bash
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic
cargo build --release
./target/release/open-agentic gateway
curl http://localhost:18789/health
```

### License

MIT License — See [LICENSE](LICENSE).

---

**OpenAgentic** — 让 AI 成为你的员工，而不是别人的产品
