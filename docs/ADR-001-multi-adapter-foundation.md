# ADR-001: 多端共同底座架构

- **状态**: Accepted
- **日期**: 2026-05-01
- **决策者**: 蔡昊伦 + Claude

## 核心产品定位(全体端共享)

**OpenAgentic 不是"AI 聊天助手",是"企业 agent 跨端中枢"。**

差异化叙事(全体端必须对齐):
1. **跨端 agent 一致性** — 飞书 / 企微 / 钉钉 / Web / Android 上的 session、记忆、工作流状态全打通
2. **Workflow 移动/IM 触发器** — 任何端一键启动企业 SOP,接 ERP/CRM/OA 真实业务系统
3. **B 端系统深度集成** — 政企数据中台/卫星数据/数据集等行业纵深(创始人转岗 AI 中台战场)
4. **位置/时间/事件驱动的 agent** — 在路上、客户现场、深夜加班都能继续工作

**绝不与 C 端 AI 聊天产品(豆包/Kimi/通义)同轨竞争**——它们做不到 1-3,我们的护城河在 B 端跨端一致性。

## 背景

OpenAgentic 当前真实状态:
- 飞书 Bot ✅ 已上线(\`extensions/channels/feishu.py\` 539 行 + systemd \`openagentic-feishu\`)
- 企微 Bot ⚠️ 骨架(294 行,wecom-cli 不存在,从未跑通)
- Web UI \`ui/\` ⚠️ 样子货(假 telegram/discord 列表;\`useWebSocket\` 连不通后端,后端无 \`/ws\`)
- Android \`extensions/android/\` ⚠️ 样子货(走 Ollama 协议,不接 agent)
- 钉钉/iOS/小程序/桌面 ❌ 0

\`extensions/channels/base.py\` 强约束 IM Webhook 范式(\`cli_binary()\` / \`verify_webhook\` / \`parse_message(body:dict)\` / \`send_message(text:str)\`),无法扩展到客户端。\`channel_runner.py\` 含飞书味硬编码(\`lark_cli\` / \`_thinking_card_msg_id\` 跨层泄漏到 \`workflow/service.py\`)。

## 决策

### 1. 四层分离

```
L4 接入
   ┌─ IM Adapter (extensions/adapters/) ─┐    ┌─ Client Gateway (src/openagentic/gateway/) ─┐
   │  飞书 / 企微 / 钉钉                   │    │  /api/* REST (CRUD)                          │
   │  webhook / SDK 长连接                 │    │  /ws (ReplyEvent 流)                         │
   └────────────────┬─────────────────────┘    └──────────────────┬───────────────────────────┘
                    └────────────┬─────────────────────────────────┘
                                 ↓ 共用
L3 底座 application/
   ConversationOrchestrator (流式事件 reply)
   Session / Identity / Intent / ToolRegistry
L2 Domain  agent / memory / workflow / knowledge (已有保持)
L1 Infra   db / llm / concurrency (已有保持)
```

**关键**: IM 走 Adapter,客户端(Web/Android)走 Gateway,**两条接入路径不同协议但共用 L3**。客户端不再假装是 adapter。

### 2. 流式事件协议

```python
async def Orchestrator.reply(session, user_text) -> AsyncIterator[ReplyEvent]
```

事件族(\`application/events.py\`):
- \`thinking\`     占位/进度    → 飞书 思考卡片;Web/Android typing;企微/钉钉 丢弃
- \`partial\`      流式 token   → Web/Android 实时渲染;IM 缓冲到 final
- \`tool_call\`    工具调用开始 → Web/Android 工具卡片;IM 可选可视化
- \`tool_result\`  工具返回     → 同上
- \`final\`        终态完整回复 → 全端必须处理
- \`error\`        异常         → 全端必须处理

各端**自行决定丢弃/渲染哪些事件**,底座一份代码服务所有端。

### 3. Adapter 协议(替代当前 \`Channel\`)

```python
class Adapter(Protocol):
    adapter_id: str   # "feishu" | "wecom" | "dingtalk" | ...
    async def start(self, orchestrator: ConversationOrchestrator) -> None: ...
    async def stop(self) -> None: ...
```

**不强制** webhook、CLI、消息格式、传输协议。

### 4. Client Gateway(新建)

\`src/openagentic/gateway/\`:
- \`api.py\`: 客户端会话 REST(send / list_session / get_message_history)
- \`ws.py\`: WebSocket endpoint,把 Orchestrator 的 ReplyEvent 流推给客户端
- 鉴权: JWT(复用 \`core/auth/\`)
- 现有 \`core/auth/router.py\` / \`core/chat/router.py\` / \`workflow/router.py\` 等 CRUD 维持

### 5. 用户身份解析下沉到底座

\`application/identity.py\`: \`(adapter_id, external_id) → user_id\`,复用 \`user_channel_bindings\` 表(platform 字段语义扩展)。Client Gateway 用 JWT 直出 user_id,不走身份解析。

### 6. Intent 抽象

\`/list /run /query /status\` 抽象成中性 Intent,IM adapter 文本匹配触发,Web/Android 按钮触发,共享同一执行链路。

### 7. 工具注册分级

- 通用工具(\`run_command\`/\`read_file\`/\`save_memory\`/8 个 workflow 工具)→ 底座默认注入
- adapter 贡献工具(\`lark_cli\` / 企微 OA / 钉钉 OA)→ adapter 启动时贡献,仅在该 adapter 会话上下文可见

### 8. 目录约定

```
src/openagentic/application/      # 底座(零 adapter 知识)
  orchestrator.py     events.py     session.py
  identity.py         intent.py     tool_registry.py

src/openagentic/gateway/           # 客户端 REST/WS 网关
  api.py              ws.py

extensions/adapters/               # 替代 channels/(channels/ 保留不删)
  base.py    registry.py
  feishu/    wecom/    dingtalk/
```

旧 \`extensions/channels/\` 保留(将来可能复用),Phase 2 飞书迁完即空置。

## 产品矩阵(P0 锁死,不再加)

| | 飞书 | 企微 | 钉钉 | Web | **Android** | 小程序 | iOS/桌面 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| S1 对话 | ✅ | ✅ | 🔄 | ✅ | **✅** | 🔄 | ✗/⏳ |
| S2 RAG | ✅ | ✅ | 🔄 | ✅ | **✅** | 🔄 | ⏳ |
| S3 工作流 | ✅ | 🔄 | ⏳ | ✅ | **✅** | ⏳ | ⏳ |
| S4 办公协同 | ✅ | 🔄 | 🔄 | 🔄 | ✗ | ✗ | ✗ |
| S5 数据分析 | ✅ | 🔄 | ✗ | ✅ | ⏳ | ✗ | ⏳ |
| S6 多智能体 | ⏳ | ⏳ | ✗ | ⏳ | ⏳ | ✗ | ⏳ |
| **触发器**(位置/时间/事件) | — | — | — | — | **✅** | — | — |
| **手机操控**(C 形态) | — | — | — | — | ⏳ | — | — |

### Android = OpenAgentic Android Endpoint(不是手机助手产品)

**定位**: OpenAgentic 在路上的一个端口,不是独立"AI 助理"。

**P0 必含**:
- 跨端会话承接(对接 Gateway WS,session 与飞书/Web 共享)
- Workflow 移动触发器(列出/启动/查看 run 状态)
- 企业 RAG 移动查询
- **位置/时间/事件触发**(地理围栏 / 特定时间 / 特定通知)→ 自动跑 workflow

**P0 选含**(单点手机能力只作为手段,不是产品定位):
- 通知拦截 → workflow 触发器输入
- 短信解析 → 提取发票/订单 → workflow 处理
- 一键唤起特定 app(Intent)+ 语音输入
- 收发邮件起草(不主动发送)

**永不做**:
- Mobile Use Agent(C 形态:跨 app UI 操控)— 字节豆包/智谱 AutoGLM 战场,单人做不出竞品级
- 纯 AI 助理对话 — 豆包/Kimi 战场,不抢

**iOS 不做**: iOS 系统不放开第三方 app 的 cross-app 自动化,物理上做不了 mobile use agent;且产品定位是 B 端跨端一致,iOS 私有 App 优先级最低。

**小程序 P1**: 微信生成式 AI 备案办下来再做。

## P0 交付盘(6 个月单人 + AI 协作上限)

| 序 | 项 | 周 | 阻断 |
|---|---|---|---|
| 1 | 共同底座 application/ + gateway/ | 2-3 | 一切前提 |
| 2 | 飞书迁底座(不破坏现状) | 1 | 验证底座 |
| 3 | Web SaaS 真接通 Gateway | 3-4 | 用 Gateway |
| 4 | 企微重写(OpenAPI,抛 wecom-cli) | 2 | 验证多端 |
| 5 | S5 数据分析骨架(飞书+Web) | 2-3 | — |
| 6 | Android Endpoint 重写 | 12-16 | 最大头,可与 5 并行 |

**合计 22-28 周 ≈ 5.5-7 个月**——已踩满 6 个月红线。**P0 锁死,任何新任务触发 #2 契约一·交付确定性红线**。

## 替代方案(已否决)

- A. 现有 \`base.py\` 打补丁: 强约束 webhook 无法扩客户端
- B. 简单 \`reply()->str\` 不做流式: Web/Android 实时渲染失效
- C. UI/Android 当作普通 adapter: 强迫客户端实现假 \`webhook\`/\`cli_binary\`
- D. 现有 \`extensions/android/\` 改造对接: 改造比重写还累(Ollama 协议要全删,聊天 UI 要重做对接 Gateway)
- E. Android 做成普通 Chat App(形态 A): 无差异化,被豆包/Kimi 碾压
- F. Android 做 mobile use agent(形态 C): 字节级研发投入,单人做不出
- G. iOS App: 物理上做不了 mobile use agent,且 B 端定位下优先级最低

## 实施 Phase

| Phase | 范围 | 是否破坏现有部署 |
|---|---|---|
| **0**(本次) | ADR + application/ + gateway/ + adapters/ 空骨架 | 否 |
| 1 | application/ 实现;飞书走兼容层调用底座 | 否,366 测试保绿 |
| 2 | 飞书 → adapter 迁移;删 channel_runner 飞书硬编码 | 一次重启验收 |
| 3 | Gateway WS/API 实现;ui/ 接通真后端 | 否 |
| 4 | 企微 adapter 重写 | 否 |
| 5 | S5 数据分析(飞书+Web) | 否 |
| 6 | Android Endpoint 重写(extensions/android/ 废弃) | 否 |
| ⏳ | 钉钉 / 小程序 / iOS 不做 / 桌面 | — |

## 不在本 ADR 范围

- 多租户存储(channel_configs → adapter_configs 升级)→ Phase 1 决定
- 跨端会话连续性数据模型 → Phase 4+
- adapter 凭据加密存储 → 多租户阶段重设计
- 产品命名(OpenAgentic / 智子 / 其他)→ 创业 0→1 启动时再定

## 参考

- \`memory/feedback-decoupling-first.md\` 解耦铁律
- \`memory/feedback-allen-discipline-pact.md\` 交付确定性契约
- 现有: \`extensions/channels/{base,channel_runner,feishu,wecom}.py\`
