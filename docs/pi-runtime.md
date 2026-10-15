# 会话树、纠偏与可嵌入 Agent

这些能力借鉴 [Pi](https://github.com/earendil-works/pi) 的设计，使用 OpenAgentic 原有 Python ReAct 循环、provider 配置和工具权限。不是 Pi 插件或会话文件格式的兼容实现。

## 保存、恢复和分支

CLI 自动保存对话、模型工具调用及结果。默认保存在 `~/.openagentic/sessions/cli.sqlite3`，按启动目录隔离。设置 `OPENAGENTIC_CLI_SESSION_DIR` 可改存储目录。数据库仅保存会话内容，不保存 provider Key 配置；内容里出现的文件、工具输出和用户输入也会被保留。

```bash
openagentic                 # 创建新会话
openagentic --continue      # 恢复当前目录最近的会话
openagentic --resume <id>   # 恢复指定会话，支持唯一 ID 前缀
```

会话内命令：

- `/session`：显示当前会话 ID。
- `/sessions` 或 `/resume`：列出当前目录的会话。
- `/resume <id>`：切换到已保存会话，继续使用当前模型配置。
- `/new`：创建新会话，旧会话保留。
- `/tree`：列出节点 ID、父节点、角色和内容预览，`*` 标记当前节点。
- `/tree <node>`：回到某个节点继续对话，新消息形成新分支，原分支保留。
- `/fork [node]`：从指定节点或当前位置复制工作上下文，创建独立会话。

分支只切换对话上下文，不回滚磁盘文件。工具调用尚未全部获得结果的节点不能直接分支。恢复中断的工具批次时，会为缺失结果补中断说明，不自动重跑工具。压缩以前的消息仍在会话树中；压缩后的工作上下文通过检查点保存。

SQLite 事务保证写入原子性；同一会话的两个进程竞争写入时，后写者会收到冲突错误，需要重新恢复会话。

## 运行中输入

- **Enter**：当前有任务时，普通文本作为纠偏；当前模型响应及整批工具调用结束后，进入下一次模型请求。
- **Alt+Enter**：作为独立后续任务排队，当前任务完成后再执行。
- 当前空闲时，两种输入都会开始新任务。
- `/` 命令仍排队顺序处理；Ctrl+C 沿用中断当前轮的行为。

纠偏不会撤销已经执行或正在执行的工具。终端需要把 Alt+Enter 发送为 Escape、Enter；部分终端需先解除该快捷键的系统绑定。

## 可执行扩展

只有显式传入的 Python 文件会执行，不会自动加载仓库里的代码：

```bash
openagentic --extension /absolute/path/project_rules.py
```

扩展入口是 `setup(api)`。扩展属于可信宿主代码，具有当前 Python 进程的权限。与 Skill 的文本指引不同，它可以注册执行逻辑：

```python
def setup(api):
    async def protect(call):
        if call["name"] in {"edit_file", "write_file", "delete_file"}:
            if "/migrations/" in call["arguments"].get("path", ""):
                return {**call, "blocked": "迁移文件受保护"}
    api.on("tool_call", protect)

    async def hello(args):
        return "hello " + args
    api.register_command("hello", hello)
    api.register_status("project", lambda: "项目规则已加载")
```

注册接口：

- `register_tool(name, description, parameters, handler, read_only=False)`：JSON Schema 参数校验；handler 接收参数字典，可同步或异步，返回文本或 JSON 数据。自定义工具每次都需要宿主确认；SDK/RPC 默认拒绝。`read_only=True` 允许在计划模式中展示。
- `register_command(name, handler)`：CLI `/name args` 或 SDK `command(name, args)`。
- `register_provider(name, complete)`：处理 `name/model` 的模型请求；complete 签名为 `(messages, model, **kwargs)`，返回与现有 `litellm_chat` 相同的 `{"message": ...}` 结构。
- `register_status(name, render)`：在 CLI 底栏显示同步返回的文本。
- `on(event, handler)`：注册有序事件处理器。

事件包括 `session_start`、`session_shutdown`、`agent_start`、`agent_end`、`message`、`tool_execution_start`、`tool_execution_end`。`context` 接收下一次模型请求的消息副本，可返回改写后的列表，不改变已保存历史。`tool_call` 接收 `name` 和 `arguments`，可改写调用或返回 `blocked`；`tool_result` 接收调用及 `result`，可返回改写后的结果。返回 `None` 表示不替换传入数据。工具钩子也适用于 Codemode 的嵌套调用。

## Codemode

默认关闭。安装可选运行时后启用：

```bash
pip install -e '.[codemode]'
openagentic --codemode
```

模型可调用 `codemode`，传入 `{"code": "..."}`。脚本运行于 QuickJS 的 WebAssembly 环境，不提供 Node、文件、网络或模块加载器；所有外部操作都经过 OpenAgentic 工具和权限检查。

```javascript
const results = await Promise.all([
  tools.read_file({path: "README.md"}),
  tools.read_file({path: "pyproject.toml"})
]);
return results.map(text => text.slice(0, 200));
```

支持 `await tools.<name>(args)`、`text(value)` 和顶层 `return`。只有脚本选择输出的数据进入模型上下文。默认最多并发 4 次工具操作；内置读取可并行，写入和确认串行。递归 Codemode、`done` 和未激活工具不可从脚本调用。

默认限制：脚本 128 KiB、JavaScript 内存 64 MiB、脚本自身计算最多 1 秒（不计异步工具等待）、整体 30 秒执行期限、64 次工具调用、单次工具结果 1 MiB、输出 10,000 字节。脚本报错或取消不会撤销已经完成的操作。此功能使用实验中的 `quickjs-rs` 可选依赖，保持显式启用。

## Python SDK

```python
from openagentic.runtime.agent import AgentSession

async with AgentSession(
    model="openai/my-model",
    api_base="http://127.0.0.1:80/v1",
    api_key="local",
    on_event=lambda event: print(event["type"]),
) as session:
    answer = await session.prompt("阅读 README 并说明如何运行")
    print(answer, session.id)
```

`prompt()` 返回当前任务及其后续排队任务完成后的最终文本。同一 Session 只能有一个运行中的 `prompt()`；运行时可调用 `steer(text)`、`follow_up(text)`、`cancel()`。支持 `tree()`、`checkout(node)`、`execute_tool(name, args)`、`command(name, args)`，构造时可传 `resume=<id>` 或 `resume="latest"`。`cwd` 用于会话分组，不改变宿主进程工具的工作目录。

可传 `extensions=Extensions()`、`confirm_fn=async_callback`、`codemode=True`。默认不渲染 CLI 内容；`output=` 可接收 Rich 文本输出，`on_event` 接收结构化事件。`message` 事件包含完整模型消息，目前不是逐 token 流。SDK 不调用交互式凭证向导，模型地址及 Key 由调用方传入。

## JSONL RPC

```bash
openagentic --mode rpc --model openai/my-model
# 也可直接使用独立模块，--api-base 在这个模块指模型 API 地址：
python -m openagentic.runtime.rpc --model openai/my-model --api-base http://127.0.0.1:80/v1
```

CLI RPC 复用已保存的 provider 配置，支持 `--extension`、`--codemode`、`--continue`、`--resume`。不支持交互式平台登录参数。stdout 只输出以 LF 分隔的 JSON，诊断信息写 stderr。消息示例：

```json
{"id":1,"method":"prompt","params":{"text":"阅读 README"}}
{"id":2,"method":"steer","params":{"text":"只检查安装步骤"}}
{"id":3,"method":"follow_up","params":{"text":"最后给出运行命令"}}
```

请求响应为 `{"id":1,"result":"..."}`，失败为 `{"id":1,"error":{"code":"...","message":"..."}}`。异步事件为 `{"event":{"type":"message","session_id":"...","message":{...}}}`。客户端必须按 ID 匹配响应，不能依赖返回顺序。

方法还有 `state`、`tree`、`checkout`（`params.node`）、`command`（`params.name` 和 `params.args`）、`cancel`、`close`。`state` 返回会话 ID、busy 状态及当前工作消息。`prompt` 的响应在整次运行结束后返回；同时可发送纠偏、追加和取消请求。`close` 或 stdin EOF 会取消运行并关闭会话。单帧上限 8 MiB。RPC 没有远程确认 UI，需确认的写入和扩展工具默认拒绝。
