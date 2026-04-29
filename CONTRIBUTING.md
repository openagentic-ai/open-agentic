# Contributing to OpenAgentic

感谢愿意为 OpenAgentic 贡献代码 / 文档 / 想法。本指南覆盖：开发环境、代码规范、提交流程、CLA 要求。

## 开发环境

参考 [README — 快速启动](README.md#快速启动)：

```bash
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d postgres
```

## 代码规范

| 类别 | 工具 / 约定 |
|---|---|
| Python lint | `ruff check src tests` |
| Python 类型检查 | `mypy` |
| 安全扫描 | `bandit -r src/openagentic -c pyproject.toml` |
| 依赖审计 | `pip-audit` |
| 测试 | `pytest -q`（基线：295 passed, 2 skipped） |

提交前请确保：
- 所有测试通过
- `ruff check` 无新告警
- 新增公开函数有类型注解
- 触及到的模块文档（如 docstring / README）同步更新

## 提交规范

### Commit 信息

参考现有提交风格（中英混排可接受）：

```
<type>[(scope)]: <主题摘要>

[详细说明，分点列出关键变更]

[Refs / Closes #issue]

Co-Authored-By: <name> <email>
```

`type` 取值：`feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `perf` / `style`

例：

```
feat(workflow): 节点连接器抽象 + HTTP 节点首发

- workflow/connectors/ 新模块，定义 BaseConnector 协议
- HTTPConnector 支持 GET/POST/PUT/DELETE，超时+重试
- 节点 schema 增加 connector_type 字段
- 新增 6 个 connector 单测
```

### Pull Request

- 一个 PR 只做一件事，避免大杂烩
- PR 描述需包含：动机 / 改动点 / 测试方式 / 风险点
- 大改动（>500 行）请先在 issue 讨论方案再写代码
- 你的 commit 必须能被独立 review，rebase 干净再提

## 分支策略

- `main`：稳定主干，保持随时可发布
- 工作分支：`feat/<topic>` / `fix/<topic>` / `refactor/<topic>`
- 长期实验：`exp/<topic>`，合并前 squash

## CLA — 贡献者许可协议

**任何被合并的代码改动都需要贡献者签署 CLA**（[cla.md](cla.md)）。

### 为什么要 CLA

- 保留项目未来调整 license 的灵活性（如从 Apache 2.0 切换到 BSL 时不用逐个征得每位 contributor 同意）
- 明确专利授权范围，保护其他贡献者和用户
- 这是 Apache 基金会、Google、Meta、Linux 基金会等几乎所有主流开源项目的标准做法

### 如何签署

**方式一（推荐，PR 自动检查）**：

未来接入 [cla-assistant.io](https://cla-assistant.io) 或 GitHub Action，PR 创建时自动提示签署。当前阶段：

**方式二（当前手动）**：

在你的第一个 PR 的描述中添加：

```
I have read [cla.md](cla.md) and agree to its terms.
Signed-off-by: Your Name <your.email@example.com>
```

或在 commit 信息中添加 DCO 签名：

```
git commit -s -m "feat: ..."
```

`-s` 会自动添加 `Signed-off-by:` 行。这表示你确认贡献符合 [Developer Certificate of Origin (DCO)](https://developercertificate.org/)。

### CLA 不要求转让版权

CLA 要求的是**许可授权**（license grant），不是版权转让。你仍然是你贡献代码的版权所有者，只是给项目维护者一份永久、全球、免费的许可来使用、修改、分发并按需重新授权。

## 沟通渠道

- GitHub Issues：bug 报告、功能讨论
- GitHub Discussions：开放讨论、设计提案
- 安全问题：请勿在 issue 公开，发邮件到仓库 owner（避免被恶意利用）

## 行为准则

简单两条：
1. 对事不对人
2. 不歧视、不骚扰

违反请反馈仓库 owner，会被严肃处理。

---

再次感谢。OpenAgentic 还在 0 到 1 阶段，**第一批 contributor 等于联合创始人**。
