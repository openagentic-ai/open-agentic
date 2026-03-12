# OpenAgentic

**OpenAgentic** — 开源 AI 手机 Agent，让 AI 帮你操作手机

一个以 Android 无障碍服务为核心的 AI Agent 平台。用户通过自然语言下达任务，AI 自动理解屏幕内容并控制手机完成操作。数据本地化、开源可审计、支持本地大模型。

## 产品定位

- **形态**：Android App（类似豆包手机 / Manus）
- **核心能力**：通过无障碍权限，AI 读取屏幕、模拟点击滑动、跨 App 执行用户任务
- **差异化**：支持 100+ 大模型 API（也支持本地 Ollama）、数据本地化、开源可审计、安全隐私优先

## 技术架构

```
Android App（Kotlin，AccessibilityService）
    ↕ HTTP / WebSocket
Rust Gateway（axum，端口 18789）
    ↕
Ollama（本地 LLM）/ 云端 LLM（OpenAI、Anthropic、DeepSeek 等）
```

## 核心特性

| 特性 | 描述 |
|------|------|
| 🤖 **多智能体系统** | Orchestrator / Researcher / Coder / Writer 等多种 Agent，支持任务自动分解与协作 |
| 🧠 **三层记忆** | 工作记忆 → 短期记忆（压缩摘要）→ 长期记忆（向量存储），per-session 隔离 |
| 📱 **手机控制** | 通过 Android 无障碍服务读取屏幕、模拟操作、跨 App 执行任务 |
| 🔐 **安全优先** | JWT 认证、安全沙箱（Docker/WASM）、输入过滤 / 输出验证 / 审计日志 |
| 🗣️ **语音交互** | STT 语音识别 + TTS 语音合成 |
| 🌐 **多平台消息** | 15+ 消息通道（Telegram、Discord、钉钉、企业微信、飞书等） |
| 🛠️ **工具生态** | 浏览器控制、定时任务、Webhook、MCP 集成 |
| 📡 **ACP 协议** | Agent Capability Protocol，分布式 Agent 能力发现与协作 |

## 项目结构

```
open-agentic/
├── crates/
│   ├── openagentic-core        # 核心类型、配置、错误
│   ├── openagentic-ai          # AI Provider 抽象（LiteLLM 统一网关，支持 100+ 厂商）
│   ├── openagentic-agent       # 多智能体系统 + 技能进化引擎
│   ├── openagentic-server      # HTTP/WebSocket Gateway + JWT 认证
│   ├── openagentic-memory      # 三层记忆系统
│   ├── openagentic-vector      # 向量存储（Qdrant/LanceDB/Milvus）
│   ├── openagentic-channels    # 消息通道集成
│   ├── openagentic-voice       # STT/TTS 语音服务
│   ├── openagentic-canvas      # 实时协作画布
│   ├── openagentic-browser     # 浏览器自动化（chromiumoxide）
│   ├── openagentic-sandbox     # Docker/WASM 安全沙箱
│   ├── openagentic-tools       # 工具系统（Cron/Webhook/MCP）
│   ├── openagentic-device      # 设备节点 + 嵌入式控制
│   ├── openagentic-security    # 安全管线
│   ├── openagentic-acp         # ACP 协议实现
│   ├── openagentic-ws          # 通用 WebSocket 模块
│   └── openagentic-cli         # CLI 命令行
└── ui/                         # Web UI（React 19 + Vite + TailwindCSS）
```

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Rust 1.93+, axum 0.8, tokio |
| **前端** | React 19, Vite, TailwindCSS, Zustand |
| **移动端** | Kotlin, Jetpack Compose, AccessibilityService |
| **AI** | LiteLLM 统一网关（OpenAI / Anthropic / Gemini / DeepSeek / Qwen / Ollama 等 100+） |
| **向量存储** | Qdrant, LanceDB, Milvus |
| **序列化** | serde + serde_json |
| **浏览器** | chromiumoxide (CDP) |
| **容器** | bollard (Docker API) |

## Android App 计划

### 功能模块

1. **对话界面** — 自然语言输入任务，AI 返回执行方案
2. **无障碍服务** — 读取屏幕内容、模拟点击/滑动/输入、跨 App 操作
3. **屏幕理解** — 截图 + 视觉模型分析界面元素
4. **任务编排** — 多步骤任务自动分解与顺序执行
5. **操作确认** — 高风险操作（支付、删除等）需用户手动确认
6. **连接管理** — 自动发现局域网 Gateway / 远程连接配置

### 技术选型

- **UI**: Jetpack Compose
- **网络**: Retrofit / OkHttp
- **异步**: Kotlin Coroutines + Flow
- **系统控制**: AccessibilityService
- **屏幕截图**: MediaProjection API
- **本地存储**: Room
- **最低版本**: Android 8.0 (API 26)

### 安全边界

- 初期不碰支付、通讯录、短信等敏感操作
- 高风险操作必须用户确认
- 数据本地存储，不上传
- 支持一键清除用户数据

## 快速开始

### 构建与运行

```bash
# 克隆项目
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic

# 构建
cargo build --release

# 启动 Gateway
cargo run --release -- gateway

# 启动 Gateway（指定端口）
cargo run --release -- gateway --port 18790

# 健康检查
curl http://localhost:18789/health
```

### CLI 命令

| 命令 | 功能 |
|------|------|
| `gateway` | 启动 HTTP/WebSocket 服务 |
| `wizard` | 交互式设置向导 |
| `doctor` | 系统健康检查 |
| `agent` | Agent 对话模式 |

## API 端点

### 认证

启用 JWT 认证后，除公开端点外所有请求需携带 `Authorization: Bearer <token>` 头。

| 端点 | 方法 | 认证 | 功能 |
|------|------|------|------|
| `/health` | GET | 公开 | 健康检查 |
| `/api/auth/login` | POST | 公开 | 登录获取 JWT token |
| `/api/auth/token` | POST | 公开 | 刷新 token |
| `/chat` | POST | 需认证 | 聊天对话 |
| `/chat/stream` | GET | 需认证 | 流式聊天（SSE） |
| `/models` | GET | 需认证 | 可用模型列表 |
| `/api/agents` | GET/POST | 需认证 | Agent 管理 |
| `/api/sessions` | GET/POST | 需认证 | 会话管理 |
| `/ws` | GET | 公开 | WebSocket 连接 |

### 登录示例

```bash
# 获取 token
curl -X POST http://localhost:18789/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# 使用 token 访问 API
curl http://localhost:18789/models \
  -H "Authorization: Bearer <token>"
```

## 配置

配置文件位于 `~/.open-agentic/config.json`：

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
    "jwt_secret": "your-secret-key-here",
    "jwt_expiration_secs": 86400
  }
}
```

> `jwt_secret` 不配置则不启用认证，所有端点均可匿名访问。

## 开发路线

- [x] 后端 Rust Gateway 编译运行
- [x] JWT 认证中间件
- [x] LiteLLM 统一 Provider（替代 12 个独立 Provider 文件）
- [ ] 对接 Ollama 测试对话
- [ ] Web UI 对接后端
- [ ] 安全加固（Argon2、HTTPS、CORS 白名单、速率限制）
- [ ] Android App 开发（Kotlin + 无障碍 API）
- [ ] 域名注册、产品上线

## 开发

```bash
# 运行测试
cargo test

# 单模块测试
cargo test -p openagentic-server

# 代码检查
cargo clippy
```

## 系统要求

- **Rust**: 1.93+
- **Docker**: 可选（沙箱功能）
- **Chrome/Chromium**: 可选（浏览器控制）
- **Android Studio**: App 开发

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。

---

**OpenAgentic** — 让 AI 助手更简单、更强大
