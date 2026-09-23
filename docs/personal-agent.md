# 本地优先个人助手验证

OpenAgentic 当前增加了一个可运行的个人助手闭环：从用户指定的本地笔记目录读取资料，生成带来源的行动简报，并保存用户偏好与上次结果。它是验证场景，不代表已经完成通用 personal agent。

## 启动

在项目根目录执行：

```bash
/opt/open-agentic/.venv/bin/python scripts/run_personal_demo.py
```

打开 `http://127.0.0.1:8765`。默认使用 `http://127.0.0.1:11434/v1` 的 OpenAI 兼容本地模型服务。模型名通过 `PERSONAL_MODEL` 指定，默认值是 `openai/local-model`。

也可以连接自己的 API key。此模式会在每次生成前提示用户，说明笔记会发送到所选服务：

```bash
PERSONAL_MODEL_MODE=api \
PERSONAL_MODEL=openai/gpt-4o \
PERSONAL_API_BASE=https://api.openai.com/v1 \
PERSONAL_API_KEY=... \
/opt/open-agentic/.venv/bin/python scripts/run_personal_demo.py
```

## 当前闭环

- 只读取启动时指定目录中的 Markdown/TXT 文件，不执行笔记中的指令。
- 工具调用只能读取目录内的文件，并限制单文件大小。
- 结果包含来源文件名，并持久化到 `data/personal-demo/latest.json`。
- 偏好写入 `data/personal-demo/memory/`，重启服务后仍然有效。
- 本地模式失败时不会静默切换到云端。
- API key 只保存在运行进程中，不写入简报和状态文件。

## 明确边界

目前还没有日历、邮件、后台提醒、跨应用操作、任务恢复或多 Agent 编排。下一步只在真实使用证明笔记简报有价值后，再增加一个高频连接器。
