---
name: security-review
description: 当用户要求"安全审查 / security review / 安全检查 / 扫一下漏洞"时使用。系统化审查代码安全缺陷，按 OWASP Top 10 + CWE 分类，给出可执行修复方案。
allowed-tools: ["read_file", "run_command"]
---

# security-review

## 何时使用
- 用户说"安全审查"、"security review"、"扫漏洞"、"有没有安全问题"
- 用户给了 PR / diff / 文件路径要求检查安全性
- 用户问"这段代码安全吗"
- **不**用于：功能 bug、性能优化、代码风格（那是 code-review 的活）

## 操作步骤

### 1. 确定审查范围
优先级从高到低：
1. 用户给了文件路径 → `read_file` 全读
2. 用户给了 PR 链接 → `gh pr diff <num>` 看完整 diff
3. 用户没说具体范围 → `run_command: git diff` 看当前未提交改动；若空则 `git diff HEAD~1`

### 2. 按"漏洞严重度"分类检查

#### 🔴 严重（可导致 RCE / 数据泄露 / 权限绕过）
- **命令注入**：`os.system()` / `subprocess` + 用户输入未过滤
- **SQL 注入**：字符串拼接 SQL、ORM raw query 拼接
- **路径穿越**：`../` 未过滤的文件读写（`Path(unsafe).resolve()` 未用）
- **反序列化**：`pickle.loads()` 接用户输入
- **硬编码凭证**：API key / password / token / secret 写死在源码或注释里
- **认证绕过**：JWT 未验证签名 / `alg=none` / 无过期检查
- **SSRF**：用户可控 URL 被服务端请求（`requests.get(user_url)`）
- **权限缺失**：端点无认证/授权注解、对象级授权缺失（user_id 未过滤）

#### 🟡 高危（可导致信息泄露 / 逻辑绕过 / 拒绝服务）
- **XSS**：未转义的 HTML 输出（前端 `dangerouslySetInnerHTML`、后端 `mark_safe`）
- **敏感信息在日志/响应中泄露**：traceback 返回到前端、密码/密钥被 log
- **CORS 配置过宽**：`allow_origins=["*"]` + `allow_credentials=True`
- **速率限制缺失**：登录/注册/验证码无频率限制
- **不安全的重定向**：`redirect(user_input)` 无白名单
- **依赖漏洞**：`pip-audit` / `npm audit` 有已知 CVE

#### 🟢 改进（纵深防御，非立即风险）
- HTTP → HTTPS 未强制（HSTS 缺失）
- Cookie 缺 `HttpOnly` / `Secure` / `SameSite`
- CSP header 未设置
- 错误消息过于详细（区分已注册/未注册用户）
- 密码策略太弱（无最小长度/复杂度要求）

### 3. 输出格式

```markdown
## Security Review: <文件名 / PR 标题>

### 🔴 严重 (N)
1. **<CWE-ID: 名称>** `<文件>:<行号>`
   ```<lang>
   <有问题的代码>
   ```
   **风险**：<攻击者如何利用，1-2 句话>
   **修复**：<具体怎么改>

### 🟡 高危 (N)
（同上格式）

### 🟢 改进 (N)
（同上格式）

### 总结
- 整体安全评级：🔴 严重风险 / 🟡 需要注意 / 🟢 基本安全
- 最紧急的 3 件事
```

## 注意事项

### 不做的事
- ❌ 不报告 linter 就能发现的低级问题（弱加密算法除外）
- ❌ 不要求完全重写架构（安全修复应最小化、外科手术式）
- ❌ 不 panic：报告安全问题时语气冷静、专业，不要制造恐慌
- ❌ 不碰生产环境：只分析代码，不给 `curl -X POST production.com` 这样的命令

### 强约束
- 每条问题**必须**标注文件路径 + 行号
- 每条问题**必须**给出可执行的修复代码（不是"建议加强安全"）
- 涉及凭据/密钥 → **必须**提醒"轮换已泄露的密钥，不要只删代码"
- 存在严重问题 → **必须先列严重问题**，不和其他级别混在一起

## 参考
- OWASP Top 10 (2021): https://owasp.org/www-project-top-ten/
- CWE Top 25: https://cwe.mitre.org/top25/
- pip-audit / safety：Python 依赖 CVE 扫描
- bandit：Python 静态安全分析
