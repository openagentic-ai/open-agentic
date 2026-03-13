# OpenAgentic

**Open-source AI phone agent** — Let AI operate your Android phone

An AI Agent platform built on Android Accessibility Services. Users describe tasks in natural language; the AI understands the screen and controls the phone to complete operations. Supports 100+ LLM APIs, local-first data, open-source and auditable.

## Architecture

```
Android App (Kotlin, Jetpack Compose)
    ↕  HTTP / SSE / WebSocket
Rust Gateway (axum + LiteLLM, port 18789)
    ↕
100+ LLM APIs (OpenAI / Anthropic / Gemini / DeepSeek / Qwen / Ollama ...)
```

## Features

- **100+ LLM support** — Unified LiteLLM gateway: OpenAI, Anthropic, Gemini, DeepSeek, Qwen, Ollama, and more
- **Multi-agent system** — Task decomposition across specialized agents (Researcher, Coder, Writer)
- **3-layer memory** — Working → short-term (compressed) → long-term (vector store)
- **Phone control** — Read screen via AccessibilityService, simulate taps/swipes/typing (planned)
- **Voice interaction** — STT speech recognition + TTS synthesis
- **Security** — JWT + Argon2 auth, input filtering, output validation, audit logging, rate limiting
- **Multi-channel** — 15+ messaging integrations (Telegram, Discord, DingTalk, WeCom, Feishu)
- **Tool ecosystem** — Browser automation, cron jobs, webhooks, MCP integration

## Quick Start

```bash
# Clone and build
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic
cargo build --release

# Start the gateway
./target/release/open-agentic gateway

# Health check
curl http://localhost:18789/health
```

### Setup Authentication

```bash
# Generate a password hash
./target/release/open-agentic hash-password YOUR_PASSWORD

# Configure ~/.openclaw-rust/config.json:
# {
#   "security": {
#     "jwt_secret": "your-random-secret-key",
#     "admin_username": "admin",
#     "admin_password_hash": "$argon2id$v=19$..."
#   }
# }

# Login
curl -X POST http://localhost:18789/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "YOUR_PASSWORD"}'

# Use the token
curl http://localhost:18789/models \
  -H "Authorization: Bearer <token>"
```

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | Public | Health check |
| `/api/auth/login` | POST | Public | Login, get JWT token |
| `/chat` | POST | Required | Chat (JSON response) |
| `/chat/stream` | GET | Required | Streaming chat (SSE) |
| `/models` | GET | Required | List available models |
| `/voice/tts` | POST | Required | Text-to-speech |
| `/voice/stt` | POST | Required | Speech-to-text |
| `/api/agents` | GET/POST | Required | Agent management |
| `/api/sessions` | GET/POST | Required | Session management |
| `/ws` | WebSocket | Public | Real-time communication |

## Configuration

Config file: `~/.openclaw-rust/config.json`

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

Without `jwt_secret`, all endpoints are accessible without authentication.

## Project Structure

```
open-agentic/
├── crates/
│   ├── openagentic-core        # Core types, config, errors
│   ├── openagentic-ai          # LiteLLM unified provider (100+ LLMs)
│   ├── openagentic-agent       # Multi-agent system + skill evolution
│   ├── openagentic-server      # HTTP/WS Gateway + JWT + rate limiting
│   ├── openagentic-memory      # 3-layer memory system
│   ├── openagentic-vector      # Vector stores (Qdrant/LanceDB/Milvus)
│   ├── openagentic-channels    # Messaging integrations
│   ├── openagentic-voice       # STT/TTS services
│   ├── openagentic-canvas      # Real-time collaborative canvas
│   ├── openagentic-browser     # Browser automation
│   ├── openagentic-sandbox     # Docker/WASM sandboxing
│   ├── openagentic-tools       # Cron/Webhook/MCP tools
│   ├── openagentic-device      # Device control
│   ├── openagentic-security    # Input filter, output validation, audit
│   ├── openagentic-acp         # Agent Capability Protocol
│   ├── openagentic-ws          # WebSocket module
│   └── openagentic-cli         # CLI entry point
├── ui/                         # Web UI (React 19 + Vite + TailwindCSS)
└── android/                    # Android App (planned)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `gateway` | Start HTTP/WebSocket server |
| `hash-password <pw>` | Generate Argon2 password hash |
| `agent` | Interactive chat mode |
| `wizard` | Interactive setup |
| `doctor` | System health check |
| `agents list/add/remove` | Manage agents |

## Roadmap

- [x] Rust Gateway with HTTP/WebSocket
- [x] LiteLLM unified provider (100+ LLMs)
- [x] JWT authentication + Argon2 password hashing
- [x] Security hardening (CORS whitelist, rate limiting, security headers)
- [ ] Ollama chat integration testing
- [ ] Web UI integration
- [ ] Android App — Phase 1: Chat MVP
- [ ] Android App — Phase 2: Screen understanding
- [ ] Android App — Phase 3: Accessibility Agent
- [ ] Public release

## Security

- **Authentication**: JWT tokens with Argon2 password hashing
- **Input protection**: Prompt injection detection (regex + keyword blacklist, multi-language)
- **Output validation**: Automatic redaction of sensitive data (API keys, passwords, credit cards)
- **Rate limiting**: Per-IP login throttling, per-token API throttling
- **CORS**: Configurable origin whitelist
- **Security headers**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy
- **Sandboxing**: Docker and WASM isolation for tool execution

## Requirements

- **Rust**: 1.93+
- **Docker**: Optional (sandbox features)
- **Chrome/Chromium**: Optional (browser automation)

## License

MIT License — See [LICENSE](LICENSE).

---

**OpenAgentic** — 让 AI 助手更简单、更强大
