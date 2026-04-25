---
name: git-commit
description: 当用户要求"提交代码 / 写 commit / git commit / 帮我 commit"时使用。生成贴合仓库历史风格的规范化 commit message，并在用户确认后真正提交。
allowed-tools: ["run_command", "read_file", "write_file"]
---

# git-commit

## 何时使用
- 用户说"提交"、"commit"、"git commit"、"帮我把这些改动提交"
- 用户准备把当前工作树改动提交到本地仓库
- **不**用于：push、pull、merge、rebase 等其他 git 操作（那些请直接用 `run_command`）

## 操作步骤

### 1. 收集上下文（并行执行 3 个命令）
```
run_command: git status
run_command: git diff --stat        # 看哪些文件改了多少
run_command: git diff --cached      # 已暂存的具体改动
run_command: git log --oneline -10  # 学仓库 commit 风格
```

### 2. 判断改动性质
基于 diff 内容推断 commit 类型，**不要瞎编**：
- `feat:` 新功能（新文件、新函数、新接口）
- `fix:` 修 bug（错误处理、边界条件修正）
- `refactor:` 重构（行为不变，结构改）
- `docs:` 文档（README、注释，无代码逻辑改动）
- `test:` 仅测试文件
- `chore:` 依赖、配置、构建脚本
- 仓库已有自定义前缀风格则**沿用**（看 git log 决定）

### 3. 起草 commit message
- **第一行**：`<type>: <一句话总结，imperative 语气，≤72 字>`
- 空一行
- **正文（可选，复杂改动才写）**：解释 why 不解释 what（diff 已经说明 what）
- 中文 / 英文跟随仓库历史风格

### 4. 给用户看草稿，等确认
**必须先把草稿打印到对话**，等用户说"提交 / 行 / yes" 再真正运行 `git commit`。
**不要直接 commit。**

### 5. 执行
```
run_command: git add <files>           # 若用户没暂存
run_command: git commit -m "<message>"
run_command: git status                # 验证
```

## 注意事项

### 危险红线
- ❌ 永远不加 `--no-verify` / `--no-gpg-sign`，除非用户明确要求
- ❌ 永远不 `git add -A` / `git add .`（可能误加 .env 等敏感文件）；先列文件再加
- ❌ 永远不 `git commit --amend`（会改写历史，除非用户明确要求）
- ❌ 检测到 `.env`、`*.pem`、`id_rsa`、`credentials.json` 等敏感文件被改时，**必须先警告用户**

### 多文件提交策略
- 改动跨多个无关主题（如同时改了 auth bug + 新加了 logging）→ 建议拆成多个 commit
- 让用户决定要不要拆，不要擅自批量提交

## 参考
- conventional commits: https://www.conventionalcommits.org/
- 当前仓库的 `git log --oneline -20` 永远是最权威的风格参考
