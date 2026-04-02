<div align="center">

# OpenAgentic

**企业私有化 AI 员工部署平台**

给你的企业招一个永不离职的 AI 员工

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Rust](https://img.shields.io/badge/Rust-1.93%2B-orange.svg)](https://www.rust-lang.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue.svg)](https://www.typescriptlang.org/)

[English](#english) | [中文](#核心理念)

</div>

---

## 核心理念

**别人的 AI 是工具，我们的 AI 是你的员工。**

OpenAgentic 为中小企业提供交钥匙式的 AI 私有化部署服务。我们帮你训练一个懂你业务的 AI 员工，部署在你自己的服务器上，数据从头到尾不出你的内网。

- 不请假、不离职、7×24 小时在岗
- 懂你的产品、价格、流程，说你们公司的话
- 数据私有化，不上传任何第三方平台
- 开源可审计，MIT 协议

## 架构总览

```
┌──────────────────────────────────────────────────────────┐
│                       用户接入层                          │
│  Web UI · Android App · CLI(oa) · 23+消息通道 · API     │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTPS / WebSocket / SSE
┌────────────────────────▼─────────────────────────────────┐
│                  OpenAgentic 引擎 (Rust)                  │
│                                                           │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
│  │ Gateway  │ │  Agent   │ │  Memory  │ │  Security   │  │
│  │ (Axum)  │ │ 调度引擎  │ │ 三层记忆  │ │ JWT+审计    │  │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────┘  │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
│  │ Channels│ │  Voice   │ │  Canvas  │ │  Sandbox    │  │
│  │ 23通道  │ │ STT/TTS  │ │ 协作画布  │ │ Docker/WASM │  │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────┘  │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                      大模型层                              │
│  Ollama · OpenAI · Anthropic · Gemini · DeepSeek ·       │
│  通义千问 · 豆包 · 智谱 · Kimi · MiniMax · OpenRouter    │
│  等 100+ 模型，LiteLLM 统一网关                           │
└──────────────────────────────────────────────────────────┘
```

## 核心能力

| 能力 | 说明 |
|------|------|
| **100+ 大模型** | LiteLLM 统一网关：OpenAI、Anthropic、Gemini、DeepSeek、通义千问、Ollama 等 13 家 Provider |
| **多 Agent 协作** | 任务自动分解，多个专业 Agent 协同工作（客服、跟单、翻译、培训） |
| **三层记忆** | 工作记忆 → 短期记忆（压缩摘要）→ 长期记忆（向量存储） |
| **向量存储** | Qdrant、LanceDB、Milvus、PgVector 四种后端可选 |
| **行业微调** | 基于你的业务数据微调模型，AI 员工越干越熟练 |
| **23+ 消息通道** | 微信、钉钉、飞书、Telegram、Discord、Slack、WhatsApp、Teams、Signal 等 |
| **安全优先** | JWT + Argon2 认证、Prompt 注入检测、输出脱敏、审计日志、速率限制 |
| **工具生态** | 浏览器自动化、定时任务、Webhook、MCP 协议集成 |
| **沙箱隔离** | Docker / WASM / Native 三种沙箱模式，工具调用安全隔离 |
| **语音交互** | STT 语音识别 + TTS 语音合成，支持语音对话 |
| **设备控制** | 摄像头、屏幕、定位、通知等硬件抽象层 |
| **协作画布** | 实时协作的可视化工作区 |

## AI 员工能胜任什么岗位

- **跨境电商客服专员** — 精通多国语言，7×24 在线，产品参数/物流/退换货张口就来
- **外贸业务跟单员** — 自动识别买家意图，匹配报价方案，生成专业英文回复
- **门店前台接待员** — 餐饮/酒店/诊所的 AI 前台，营业时间/预约/价格自动应答
- **内部培训讲师** — 公司文档/SOP/制度全部学会，新员工有问必答

## 快速开始

### 方式一：Rust 网关（推荐）

```bash
# 克隆并构建
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic
cargo build --release

# 初始化配置
./target/release/open-agentic init

# 交互式配置向导（选择 Provider、模型、安全设置等）
./target/release/open-agentic wizard

# 启动网关
./target/release/open-agentic gateway

# 健康检查
curl http://localhost:18789/health
```

### 方式二：CLI 交互对话

```bash
# 安装 CLI（需要 Node.js 20+）
cd packages/cli
npm install && npm run build
npm link

# 交互模式 — 直接在终端和 AI 对话
oa

# 单次问答模式 — 适合脚本和管道
oa -p "用 Python 写一个快速排序"

# 指定模型
oa -p "翻译成英文：你好世界" -m qwen3:4b

# 查看可用模型
oa models

# 检查连接状态
oa status
```

**CLI 交互模式示例：**

```
$ oa

  OpenAgentic CLI v0.1.0

✓ API: http://localhost:11434/v1
  Model: qwen3:14b

  Type /help for commands, Ctrl+C to exit.

> 你好，介绍一下你自己
你好！我是 OpenAgentic AI 助手，可以帮你回答问题、写代码、翻译文档等。

> /models
  Available models:
 ● qwen3:14b
   qwen3:4b
   deepseek-r1:32b

> /help
  Commands:
  /help        Show this help message
  /clear       Clear conversation history
  /model       Show or switch model (/model <name>)
  /models      List available models
  /status      Check API connectivity
  /quit        Exit
```

### 配置认证

```bash
# 生成密码哈希
./target/release/open-agentic hash-password YOUR_PASSWORD

# 编辑 ~/.openclaw-rust/config.json，填入 jwt_secret、admin_username、admin_password_hash

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
| `/chat` | POST | 需要 | 对话（JSON 请求/响应） |
| `/chat/stream` | GET | 需要 | 流式对话（SSE，逐 token 返回） |
| `/models` | GET | 需要 | 可用模型列表 |
| `/voice/tts` | POST | 需要 | 文字转语音 |
| `/voice/stt` | POST | 需要 | 语音转文字 |
| `/api/agents` | GET/POST | 需要 | Agent 管理（列表/创建） |
| `/api/agents/{id}` | GET | 需要 | Agent 详情 |
| `/api/agent/message` | POST | 需要 | 向 Agent 发送消息 |
| `/api/sessions` | GET/POST | 需要 | 会话管理（列表/创建） |
| `/api/sessions/{id}` | GET | 需要 | 会话详情 |
| `/api/sessions/{id}/close` | POST | 需要 | 关闭会话 |
| `/api/channels` | GET/POST | 需要 | 通道管理 |
| `/api/channels/{id}` | DELETE | 需要 | 删除通道 |
| `/api/presence` | GET/POST | 需要 | 用户在线状态 |
| `/ws` | WebSocket | 公开 | 实时双向通信 |

### 对话 API 示例

```bash
# 非流式对话
curl -X POST http://localhost:18789/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "你好",
    "agent_id": "orchestrator",
    "session_id": "optional-session-id"
  }'

# 流式对话（SSE）
curl "http://localhost:18789/chat/stream?message=你好&agent_id=orchestrator"
# 返回格式：
# data: 你
# data: 好
# data: ！
# data: 有什么
# data: 可以帮你的吗？
```

## 配置

### 服务端配置

配置文件路径：`~/.openclaw-rust/config.json`

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 18789,
    "log_level": "info",
    "enable_agents": true,
    "enable_channels": false,
    "enable_voice": false,
    "enable_canvas": false,
    "enable_agentic_rag": false,
    "enable_evolution": false
  },
  "ai": {
    "default_provider": "ollama",
    "providers": [
      {
        "name": "ollama",
        "base_url": "http://localhost:11434",
        "default_model": "qwen3:14b"
      },
      {
        "name": "openai",
        "api_key": "sk-...",
        "default_model": "gpt-4o"
      },
      {
        "name": "anthropic",
        "api_key": "sk-ant-...",
        "default_model": "claude-sonnet-4-20250514"
      }
    ]
  },
  "memory": {
    "backend_type": "hybrid",
    "working": { "max_tokens": 4096 },
    "short_term": { "compression": true },
    "long_term": { "vector_backend": "qdrant" }
  },
  "security": {
    "jwt_secret": "your-secret-key",
    "jwt_expiration_secs": 86400,
    "admin_username": "admin",
    "admin_password_hash": "$argon2id$...",
    "cors_origins": ["http://localhost:3000"],
    "login_rate_limit": 5,
    "api_rate_limit": 10
  },
  "sandbox": {
    "enabled": true,
    "default_type": "docker",
    "timeout_secs": 30,
    "memory_limit_mb": 256
  }
}
```

### CLI 配置

配置文件路径：`~/.openagentic/cli.json`

```json
{
  "apiUrl": "http://localhost:11434/v1",
  "model": "qwen3:14b",
  "systemPrompt": "You are OpenAgentic AI assistant. Be helpful, concise, and accurate."
}
```

CLI 配置命令：

```bash
# 查看配置
oa config

# 修改 API 地址（如连接远程服务器）
oa config set apiUrl http://192.168.1.100:11434/v1

# 修改默认模型
oa config set model deepseek-r1:32b
```

## 消息通道

OpenAgentic 支持 23+ 消息通道，覆盖国内外主流 IM 平台：

| 分类 | 通道 |
|------|------|
| **国内** | 钉钉 (DingTalk) · 企业微信 (WeCom) · 飞书 (Feishu) |
| **国际** | Telegram · Discord · Slack · WhatsApp · Signal · Microsoft Teams · Google Chat |
| **Apple** | iMessage · BlueBubbles |
| **其他** | Matrix · Email · SMS · WebChat (Webhook) · Zalo · Zalo Personal |

通道配置示例 (`channels.yaml`)：

```yaml
enabled: true
channel_to_agent_map:
  telegram: "customer-service"
  dingtalk: "internal-assistant"
  discord: "community-bot"
config:
  telegram:
    enabled: true
    bot_token: "123456:ABC-DEF..."
    webhook_url: "https://your-domain.com/webhook/telegram"
  dingtalk:
    enabled: true
    app_key: "..."
    app_secret: "..."
```

## 项目结构

```
open-agentic/
├── crates/                              # Rust 后端（17 个模块化 Crate）
│   ├── openagentic-core        (2,874)  # 核心类型、配置加载、错误处理
│   ├── openagentic-ai          (2,937)  # LiteLLM 统一 Provider（13 家厂商）
│   ├── openagentic-agent      (30,101)  # 多 Agent 系统、技能进化、任务调度
│   ├── openagentic-server     (12,502)  # HTTP/WS 网关、Axum 路由、JWT 认证
│   ├── openagentic-memory      (9,322)  # 三层记忆（工作/短期/长期）、混合检索
│   ├── openagentic-vector      (2,097)  # 向量存储（Qdrant/LanceDB/Milvus/PgVector）
│   ├── openagentic-channels    (9,745)  # 23+ 消息通道集成
│   ├── openagentic-voice       (6,804)  # STT 语音识别 + TTS 语音合成
│   ├── openagentic-canvas      (1,997)  # 实时协作画布
│   ├── openagentic-browser     (1,502)  # Chrome 浏览器自动化
│   ├── openagentic-sandbox     (7,593)  # Docker/WASM/Native 沙箱隔离
│   ├── openagentic-tools       (6,117)  # 定时任务、Webhook、MCP 协议
│   ├── openagentic-device     (10,413)  # 设备抽象（摄像头/屏幕/定位/通知）
│   ├── openagentic-security    (2,983)  # Prompt 注入检测、输出脱敏、审计
│   ├── openagentic-acp         (1,525)  # Agent Communication Protocol
│   ├── openagentic-ws            (682)  # WebSocket 模块
│   └── openagentic-cli         (5,460)  # Rust CLI 入口（gateway/wizard/doctor/daemon）
│                              ────────
│                        总计 114,654 行 Rust
│
├── ui/                                  # Web UI（React 19 + Vite + TailwindCSS）
│   └── src/                    (2,158)  # 15 个 TS/TSX 文件
│       ├── components/                  # ChatView · Sidebar · AgentPanel · Canvas
│       ├── pages/                       # Channels · Devices · Sessions · Settings · Skills
│       └── store/                       # Zustand 状态管理
│
├── packages/                            # 独立工具包
│   └── cli/                             # 交互式 CLI 客户端 (oa 命令)
│       └── src/                         # TypeScript, 5 个源文件
│           ├── index.ts                 # Commander.js 入口
│           ├── client.ts                # OpenAI 兼容 API 客户端 (SSE 流式)
│           ├── repl.ts                  # 交互式 REPL (readline)
│           ├── config.ts                # CLI 配置管理
│           └── utils.ts                 # 终端样式
│
├── extensions/                          # 扩展
│   └── android/                 (860)   # Android App (Kotlin, Jetpack Compose)
│       └── app/src/                     # 6 个 Kotlin 文件
│           ├── MainActivity.kt          # 主界面
│           ├── ChatViewModel.kt         # 对话状态管理
│           ├── ChatScreen.kt            # 聊天 UI (Compose)
│           ├── ApiClient.kt             # Gateway HTTP 客户端
│           ├── GatewayApi.kt            # API 接口定义
│           └── LocaleHelper.kt          # 中英文切换
│
├── skills/                              # 技能定义 (YAML)
│   ├── feishu_multi_account/            # 飞书多账号管理
│   ├── openclaw_config/                 # 配置管理技能
│   └── software_development_workflow/   # 软件开发工作流
│
├── Cargo.toml                           # Rust workspace 配置
├── Cargo.lock                           # 依赖锁定
└── LICENSE                              # MIT License
```

## Rust CLI 命令

```bash
open-agentic [COMMAND]

# 服务管理
  gateway          启动 HTTP/WebSocket 网关服务（默认端口 18789）
  daemon           后台守护进程管理（start/stop/restart/status/install）
  init             初始化配置文件
  wizard           交互式配置向导
  doctor           系统健康检查（检测依赖、端口、配置）

# Agent & 对话
  agent            直接和 AI 助手对话
  agents           管理 Agent（list/add/remove）
  message          发送消息到指定通道
  skill            技能市场管理

# 配置 & 工具
  api-key          管理 API Key
  channel          管理消息通道配置
  voice            语音命令（STT/TTS）
  hash-password    生成 Argon2 密码哈希
  evo              自演化系统（实验性）
  version          显示版本信息
```

## 安全体系

| 层级 | 机制 | 说明 |
|------|------|------|
| **认证** | JWT + Argon2 | Token 认证，密码哈希存储，可配置过期时间 |
| **输入防护** | Prompt 注入检测 | 正则 + 关键词黑名单，多语言支持 |
| **输出校验** | 自动脱敏 | API Key、密码、银行卡号、身份证号自动过滤 |
| **速率限制** | 双层限流 | 登录接口 + API 接口独立限流，按 IP 计数 |
| **CORS** | 白名单 | 可配置的来源白名单，默认仅允许同源 |
| **安全头** | 全套防护 | X-Content-Type-Options、X-Frame-Options、CSP、Referrer-Policy |
| **沙箱** | 三模式隔离 | Docker（强隔离）、WASM（轻量）、Native（开发用） |
| **审计** | 操作日志 | 关键操作记录，可追溯 |

## 支持的 AI 模型 Provider

| Provider | 类型 | 代表模型 |
|----------|------|---------|
| **Ollama** | 本地部署 | Qwen3、DeepSeek-R1、Llama 3、Gemma 等 |
| **OpenAI** | API | GPT-4o、GPT-4o-mini、o1 |
| **Anthropic** | API | Claude Opus 4、Claude Sonnet 4 |
| **Google** | API | Gemini 2.5 Pro、Gemini 2.5 Flash |
| **Azure** | API | Azure OpenAI 全系列 |
| **DeepSeek** | API | DeepSeek-V3、DeepSeek-R1 |
| **OpenRouter** | 聚合 | 200+ 模型统一接入 |
| **通义千问 (Qwen)** | API | Qwen-Max、Qwen-Plus |
| **豆包 (Doubao)** | API | 豆包大模型 |
| **智谱 (GLM)** | API | GLM-4、GLM-4V |
| **Kimi (Moonshot)** | API | Moonshot-v1-128k |
| **MiniMax** | API | abab6.5 |

## Android App

实验性 Android 客户端，使用 Kotlin + Jetpack Compose 构建。

- **包名**：`ai.openagentic.app`
- **APK 大小**：17 MB
- **最低版本**：Android 8.0+
- **功能**：对话界面、Gateway 连接、中英文切换
- **构建**：`cd extensions/android && ./gradlew assembleDebug`

## 开发路线

### 已完成

- [x] Rust 后端网关编译运行（114,654 行 Rust）
- [x] LiteLLM 统一 Provider（13 家厂商 100+ 模型）
- [x] JWT 认证 + Argon2 密码哈希
- [x] 安全加固（CORS、速率限制、安全头、Prompt 注入检测、输出脱敏）
- [x] Web UI 基础框架（React 19 + Vite + TailwindCSS）
- [x] Android App Phase 1 — 对话 MVP（17MB APK）
- [x] CLI 交互工具 `oa`（流式对话、模型切换、配置管理）
- [x] 三层记忆系统框架（工作/短期/长期）
- [x] 向量存储支持（Qdrant/LanceDB/Milvus/PgVector）
- [x] 23+ 消息通道集成框架
- [x] 沙箱隔离（Docker/WASM/Native）
- [x] 语音 STT/TTS 框架
- [x] 设备控制抽象层

### 进行中

- [ ] **MCP 协议深度集成** — 可插拔的 MCP Server 发现与连接，企业级 MCP 配置管理
- [ ] **多层权限模型** — 组织策略 > 项目规则 > 用户偏好，工具级别权限控制与审计
- [ ] **Hook 生命周期系统** — 可配置的 pre/post-sampling、tool-use 钩子，企业合规检查无需改代码
- [ ] **Agent 团队/Swarm 架构** — 父子 Agent 继承关系，共享 MCP 连接，独立对话记录
- [ ] **会话持久化** — 对话历史存储与恢复，后台自动提取关键信息到记忆文件
- [ ] **结构化 I/O (SDK 模式)** — JSON-RPC 协议支持，Agent 可嵌入 CI/CD 和企业工作流
- [ ] **工具注册系统** — 声明式工具定义（schema + permissions + call），运行时验证

### 待开始

- [ ] Web UI 对接后端（完整对话界面）
- [ ] 行业微调模型集成
- [ ] Docker 容器化一键部署
- [ ] 多渠道消息实际接入（微信/钉钉/飞书 Bot Token 配置）
- [ ] Android Phase 2 — 屏幕理解（MediaProjection + 视觉模型）
- [ ] Android Phase 3 — 无障碍 Agent（AccessibilityService + LLM 规划）
- [ ] 企业管理后台（多租户、用量统计、账单）
- [ ] 种子客户落地验证

## 系统要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| **Rust** | 1.93+ | 后端编译 |
| **Node.js** | 20+ | CLI 工具、Web UI 构建 |
| **Ollama** | 可选 | 本地大模型部署 |
| **Docker** | 可选 | 沙箱隔离、容器化部署 |
| **Chrome/Chromium** | 可选 | 浏览器自动化 |

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。

---

## English

<div align="center">

**OpenAgentic** — Enterprise Private AI Employee Deployment Platform

Deploy AI "employees" inside your company's infrastructure. Your data never leaves your network.

</div>

### Key Features

- **100+ LLM Support** — Unified gateway: OpenAI, Anthropic, Gemini, DeepSeek, Qwen, Ollama, and 13 providers total
- **Multi-Agent System** — Task decomposition across specialized agents with skill evolution
- **Three-Layer Memory** — Working → Short-term (compressed) → Long-term (vector storage)
- **23+ Messaging Channels** — Telegram, Discord, Slack, WhatsApp, DingTalk, WeCom, Feishu, Teams, Signal, and more
- **Interactive CLI** — `oa` command with streaming chat, model switching, REPL mode
- **Android App** — Experimental Kotlin/Compose mobile client (17MB APK)
- **Security First** — JWT + Argon2 auth, prompt injection detection, output sanitization, audit logging, rate limiting
- **Sandbox Isolation** — Docker / WASM / Native sandboxing for tool execution
- **Voice** — STT + TTS for voice-based interaction
- **Private Deployment** — Runs on your own servers, data never leaves your network
- **Open Source** — MIT License, fully auditable

### Quick Start

```bash
# Clone and build
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic
cargo build --release

# Start gateway
./target/release/open-agentic gateway

# Health check
curl http://localhost:18789/health

# Or use the interactive CLI (requires Node.js 20+)
cd packages/cli && npm install && npm run build && npm link
oa                        # interactive REPL
oa -p "Hello, world!"    # one-shot mode
oa models                 # list available models
```

### Codebase

- **Rust backend**: 114,654 lines across 17 crates
- **Web UI**: React 19 + Vite + TailwindCSS (2,158 lines)
- **Android**: Kotlin + Jetpack Compose (860 lines)
- **CLI**: TypeScript + Commander.js (5 source files)

### License

MIT License — See [LICENSE](LICENSE).

---

<div align="center">

**OpenAgentic** — 让 AI 成为你的员工，而不是别人的产品

</div>
